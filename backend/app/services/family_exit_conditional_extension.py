from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.domain.broker import BrokerSymbolSpec, PositionSizeRequest
from app.domain.family_exit_challenger import (
    ExitChallengerWindowMetrics,
    FamilyExitChallengerReport,
)
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
    TradeOutcome,
)
from app.domain.trading import Side
from app.services.capital_risk import size_position
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.opportunity_backtester import _simulate_candidate
from app.services.opportunity_strategies import generate_candidates
from app.services.probe_review import default_probe_review_split
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.runtime_capital import resolve_demo_sizing_capital
from app.services.trailing_manager import _directional_closes

HYPOTHESIS_ID = "xau_sd_extend_2r_if_prior_3_m5_directional_v1"
CHAMPION_TARGET_R = 1.5
CHALLENGER_TARGET_R = 2.0
MAX_HOLDING_BARS = 12
STRUCTURE_WINDOW = 3
QUALIFICATION_RULE = (
    "when 1.5R is first touched, the previous three fully closed M5 bars "
    "must have strictly directional closes in trade direction"
)


def simulate_conditional_extension(
    bars: Sequence[MarketBar],
    candidate: OpportunityCandidate,
    spec: BrokerSymbolSpec,
    *,
    capital_eur: float,
    requested_risk_fraction: float,
    slippage_spread_fraction: float,
) -> tuple[TradeOutcome, bool]:
    if candidate.entry_index >= len(bars):
        raise ValueError("missing entry bar")
    entry_bar = bars[candidate.entry_index]
    spread = spec.spread
    slippage = spread * slippage_spread_fraction
    if candidate.side is Side.BUY:
        entry = entry_bar.open + spread + slippage
        stop = candidate.structural_stop
        risk_distance = entry - stop
    else:
        entry = entry_bar.open - slippage
        stop = candidate.structural_stop + spread
        risk_distance = stop - entry
    if risk_distance <= 0:
        raise ValueError("invalid stop geometry")
    sizing = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=entry,
            stop=stop,
            requested_risk_fraction=requested_risk_fraction,
            capital_eur=capital_eur,
        )
    )
    if not sizing.approved:
        raise ValueError(sizing.reason)

    champion_target = (
        entry + CHAMPION_TARGET_R * risk_distance
        if candidate.side is Side.BUY
        else entry - CHAMPION_TARGET_R * risk_distance
    )
    extended_target = (
        entry + CHALLENGER_TARGET_R * risk_distance
        if candidate.side is Side.BUY
        else entry - CHALLENGER_TARGET_R * risk_distance
    )
    last_index = min(
        len(bars) - 1,
        candidate.entry_index + MAX_HOLDING_BARS - 1,
    )
    seen_closed: list[MarketBar] = []
    extension_active = False
    qualified = False
    exit_index = last_index
    result_r: float | None = None
    exit_reason = "timeout"

    for index in range(candidate.entry_index, last_index + 1):
        bar = bars[index]
        directional = (
            len(seen_closed) >= STRUCTURE_WINDOW
            and _directional_closes(
                seen_closed[-STRUCTURE_WINDOW:],
                candidate.side,
            )
        )
        if candidate.side is Side.BUY:
            stop_hit = bar.low <= stop
            champion_hit = bar.high >= champion_target
            extended_hit = bar.high >= extended_target
        else:
            ask_high = bar.high + spread
            ask_low = bar.low + spread
            stop_hit = ask_high >= stop
            champion_hit = ask_low <= champion_target
            extended_hit = ask_low <= extended_target

        # Same conservative ordering as the canonical backtester.
        if stop_hit:
            result_r = -1.0
            exit_reason = "stop"
            exit_index = index
            break
        if extension_active:
            if extended_hit:
                result_r = CHALLENGER_TARGET_R
                exit_reason = "extended_target"
                exit_index = index
                break
        elif champion_hit:
            if directional:
                extension_active = True
                qualified = True
                if extended_hit:
                    result_r = CHALLENGER_TARGET_R
                    exit_reason = "extended_target"
                    exit_index = index
                    break
            else:
                result_r = CHAMPION_TARGET_R
                exit_reason = "target"
                exit_index = index
                break
        seen_closed.append(bar)

    if result_r is None:
        last = bars[last_index]
        if candidate.side is Side.BUY:
            result_r = (last.close - entry) / risk_distance
        else:
            result_r = (entry - (last.close + spread)) / risk_distance

    return (
        TradeOutcome(
            symbol=candidate.symbol,
            mechanism=candidate.mechanism,
            side=candidate.side,
            signal_at=candidate.signal_at,
            entry_at=candidate.entry_at,
            exit_at=bars[exit_index].timestamp,
            lots=sizing.lots,
            risk_eur=sizing.expected_loss_eur,
            result_r=result_r,
            pnl_eur=result_r * sizing.expected_loss_eur,
            execution_cost_r=(spread + slippage) / risk_distance,
            exit_reason=exit_reason,
        ),
        qualified,
    )


def _profit_factor(values: Sequence[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)


def _drawdown(values: Sequence[float]) -> float:
    equity = peak = maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _window_metrics(
    pairs: Sequence[tuple[TradeOutcome, TradeOutcome, bool]],
) -> ExitChallengerWindowMetrics:
    champion = [left.result_r for left, _, _ in pairs]
    challenger = [right.result_r for _, right, _ in pairs]
    champion_reasons = Counter(left.exit_reason for left, _, _ in pairs)
    challenger_reasons = Counter(right.exit_reason for _, right, _ in pairs)
    count = len(pairs)
    champion_total = sum(champion)
    challenger_total = sum(challenger)
    return ExitChallengerWindowMetrics(
        paired_trades=count,
        champion_total_r=champion_total,
        challenger_total_r=challenger_total,
        delta_total_r=challenger_total - champion_total,
        champion_expectancy_r=champion_total / count if count else 0.0,
        challenger_expectancy_r=challenger_total / count if count else 0.0,
        champion_profit_factor=_profit_factor(champion),
        challenger_profit_factor=_profit_factor(challenger),
        champion_max_drawdown_r=_drawdown(champion),
        challenger_max_drawdown_r=_drawdown(challenger),
        champion_targets=champion_reasons["target"],
        challenger_targets=challenger_reasons["target"] + challenger_reasons["extended_target"],
        champion_stops=champion_reasons["stop"],
        challenger_stops=challenger_reasons["stop"],
        champion_timeouts=champion_reasons["timeout"],
        challenger_timeouts=challenger_reasons["timeout"],
        extension_qualified=sum(qualified for _, _, qualified in pairs),
    )


def _paired_outcomes(
    bars_m5: Sequence[MarketBar],
    candidates: Sequence[OpportunityCandidate],
    config: OpportunityBacktestConfig,
) -> list[tuple[TradeOutcome, TradeOutcome, bool]]:
    pairs: list[tuple[TradeOutcome, TradeOutcome, bool]] = []
    busy_until = -1
    for raw in candidates:
        if raw.entry_index <= busy_until:
            continue
        if active_macro_blackouts(config.macro_events, raw.entry_at):
            continue
        champion_candidate = raw.model_copy(
            update={"target_r": CHAMPION_TARGET_R, "max_holding_bars": MAX_HOLDING_BARS}
        )
        champion, champion_exit, rejection = _simulate_candidate(
            bars_m5, champion_candidate, config
        )
        if rejection is not None or champion is None or champion_exit is None:
            continue
        challenger, qualified = simulate_conditional_extension(
            bars_m5,
            champion_candidate,
            config.spec,
            capital_eur=config.capital_eur,
            requested_risk_fraction=config.requested_risk_fraction,
            slippage_spread_fraction=config.slippage_spread_fraction,
        )
        pairs.append((champion, challenger, qualified))
        busy_until = champion_exit
    return pairs


def build_xau_structural_displacement_conditional_extension(
    files_dir: Path,
    *,
    generated_at: datetime,
    risk_fraction: float,
    research_execution_model_path: Path,
    macro_events_path: Path,
) -> FamilyExitChallengerReport:
    symbol = "XAUUSD"
    mechanism = OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or capital.capital_eur <= 0:
        raise ValueError("MT4 DEMO sizing capital is unavailable")
    spec = get_mt4_symbol_spec(files_dir, symbol)
    if spec is None:
        raise ValueError("XAUUSD broker symbol spec is unavailable")
    execution_model = load_research_execution_model(research_execution_model_path)
    if execution_model is not None:
        spec = apply_research_execution_model(spec, execution_model)
    bars_m5 = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5), symbol, Timeframe.M5
    )
    bars_m15 = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M15), symbol, Timeframe.M15
    )
    if not bars_m5 or not bars_m15:
        raise ValueError("XAUUSD M5 and M15 histories are required")
    split = default_probe_review_split()
    config = OpportunityBacktestConfig(
        spec=spec,
        mechanism=mechanism,
        split=split,
        requested_risk_fraction=risk_fraction,
        capital_eur=capital.capital_eur,
        slippage_spread_fraction=0.25,
        macro_events=load_macro_events(macro_events_path),
    )
    candidates = generate_candidates(bars_m5, bars_m15, mechanism)
    pairs = _paired_outcomes(bars_m5, candidates, config)
    validation = [
        pair for pair in pairs
        if split.train_end <= pair[0].signal_at < split.validation_end
    ]
    holdout = [pair for pair in pairs if pair[0].signal_at >= split.validation_end]
    return FamilyExitChallengerReport(
        generated_at=generated_at,
        symbol=symbol,
        strategy_id=f"{symbol}:{mechanism.value}",
        hypothesis_id=HYPOTHESIS_ID,
        change_axis="conditional_target_extension",
        champion_target_r=CHAMPION_TARGET_R,
        challenger_target_r=CHALLENGER_TARGET_R,
        max_holding_bars=MAX_HOLDING_BARS,
        capital_eur=capital.capital_eur,
        capital_source=capital.source.value,
        validation=_window_metrics(validation),
        holdout=_window_metrics(holdout),
        authority_effect=False,
        human_review_required=True,
        qualification_rule=QUALIFICATION_RULE,
        limitations=[
            "Champion cohort is frozen by the canonical 1.5R overlap policy.",
            "Signal, entry, structural stop, sizing, costs and 12-M5 horizon are identical.",
            "Only target handling changes, and only after a causal three-close directional condition.",
            "This replay is Research-only and cannot alter PAPER or broker authority.",
        ],
    )

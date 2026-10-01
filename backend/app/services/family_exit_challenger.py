from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.domain.family_exit_challenger import (
    ExitChallengerWindowMetrics,
    FamilyExitChallengerReport,
)
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
    TradeOutcome,
)
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

HYPOTHESIS_ID = "xau_sd_fixed_target_1_5r_vs_2r_exit_v1"
CHAMPION_TARGET_R = 1.5
CHALLENGER_TARGET_R = 2.0
MAX_HOLDING_BARS = 12


def _profit_factor(values: Sequence[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    if losses > 0:
        return gains / losses
    return 99.0 if gains > 0 else 0.0


def _drawdown(values: Sequence[float]) -> float:
    equity = peak = maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _window_metrics(
    pairs: Sequence[tuple[TradeOutcome, TradeOutcome]],
) -> ExitChallengerWindowMetrics:
    champion = [left.result_r for left, _ in pairs]
    challenger = [right.result_r for _, right in pairs]
    champion_reasons = Counter(left.exit_reason for left, _ in pairs)
    challenger_reasons = Counter(right.exit_reason for _, right in pairs)
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
        challenger_targets=challenger_reasons["target"],
        champion_stops=champion_reasons["stop"],
        challenger_stops=challenger_reasons["stop"],
        champion_timeouts=champion_reasons["timeout"],
        challenger_timeouts=challenger_reasons["timeout"],
    )


def _paired_outcomes(
    bars_m5,
    candidates: Sequence[OpportunityCandidate],
    config: OpportunityBacktestConfig,
) -> list[tuple[TradeOutcome, TradeOutcome]]:
    pairs: list[tuple[TradeOutcome, TradeOutcome]] = []
    busy_until = -1
    for raw in candidates:
        if raw.entry_index <= busy_until:
            continue
        if active_macro_blackouts(config.macro_events, raw.entry_at):
            continue
        champion_candidate = raw.model_copy(
            update={
                "target_r": CHAMPION_TARGET_R,
                "max_holding_bars": MAX_HOLDING_BARS,
            }
        )
        champion, champion_exit, rejection = _simulate_candidate(
            bars_m5, champion_candidate, config
        )
        if rejection is not None or champion is None or champion_exit is None:
            continue
        challenger_candidate = raw.model_copy(
            update={
                "target_r": CHALLENGER_TARGET_R,
                "max_holding_bars": MAX_HOLDING_BARS,
            }
        )
        challenger, _, challenger_rejection = _simulate_candidate(
            bars_m5, challenger_candidate, config
        )
        if challenger_rejection is not None or challenger is None:
            raise ValueError(
                "paired challenger could not be simulated on champion cohort"
            )
        pairs.append((champion, challenger))
        busy_until = champion_exit
    return pairs


def build_xau_structural_displacement_exit_challenger(
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
    execution_model = load_research_execution_model(
        research_execution_model_path
    )
    if execution_model is not None:
        spec = apply_research_execution_model(spec, execution_model)
    bars_m5 = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    bars_m15 = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M15),
        symbol,
        Timeframe.M15,
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
        pair
        for pair in pairs
        if split.train_end <= pair[0].signal_at < split.validation_end
    ]
    holdout = [pair for pair in pairs if pair[0].signal_at >= split.validation_end]
    return FamilyExitChallengerReport(
        generated_at=generated_at,
        symbol=symbol,
        strategy_id=f"{symbol}:{mechanism.value}",
        hypothesis_id=HYPOTHESIS_ID,
        change_axis="fixed_target_r",
        champion_target_r=CHAMPION_TARGET_R,
        challenger_target_r=CHALLENGER_TARGET_R,
        max_holding_bars=MAX_HOLDING_BARS,
        capital_eur=capital.capital_eur,
        capital_source=capital.source.value,
        validation=_window_metrics(validation),
        holdout=_window_metrics(holdout),
        authority_effect=False,
        human_review_required=True,
        limitations=[
            "Champion cohort is frozen by the canonical 1.5R overlap policy.",
            "Signal, entry, structural stop, sizing, costs and 12-M5 horizon are identical.",
            "Only the fixed target changes from 1.5R to 2.0R.",
            "This replay is Research-only and cannot alter PAPER or broker authority.",
        ],
    )

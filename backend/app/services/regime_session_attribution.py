from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityMechanism,
    TradeOutcome,
)
from app.domain.regime import MarketRegime
from app.domain.regime_session_attribution import (
    AttributionDimension,
    AttributionWindow,
    RegimeSessionAttributionBucket,
    RegimeSessionAttributionReport,
)
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.opportunity_backtester import _simulate_candidate
from app.services.opportunity_strategies import generate_candidates
from app.services.probe_review import default_probe_review_split
from app.services.regime import classify_regime
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.runtime_capital import resolve_demo_sizing_capital
from app.services.session_landmarks import active_session_at

SYMBOL = "XAUUSD"
MECHANISM = OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
SESSION_PARTITION = ("asia", "london", "us", "transition")
REGIME_PARTITION = tuple(MarketRegime)


def _bucket(
    *,
    window: AttributionWindow,
    dimension: AttributionDimension,
    key: str,
    outcomes: Sequence[TradeOutcome],
) -> RegimeSessionAttributionBucket:
    values = [row.result_r for row in outcomes]
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return RegimeSessionAttributionBucket(
        window=window,
        dimension=dimension,
        key=key,
        trades=len(values),
        wins=sum(value > 0 for value in values),
        losses=sum(value < 0 for value in values),
        total_r=sum(values),
        expectancy_r=(sum(values) / len(values) if values else None),
        profit_factor=(
            gains / losses if losses > 0 else 99.0 if gains > 0 else None
        ),
        max_drawdown_r=drawdown,
        average_execution_cost_r=(
            sum(row.execution_cost_r for row in outcomes) / len(outcomes)
            if outcomes
            else None
        ),
    )


def _regime_at(
    bars_m15: Sequence[MarketBar],
    at: datetime,
) -> MarketRegime:
    closed = [
        bar
        for bar in bars_m15
        if bar.timestamp + timedelta(minutes=15) <= at
    ]
    if not closed:
        return MarketRegime.WARMUP
    # classify_regime needs 50 ATR observations plus their 14-bar lookback.
    # Seventy fully closed M15 bars preserve that causal state without replaying
    # the full history for every historical trade.
    return classify_regime(closed[-70:]).regime


def _replay_outcomes(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    config: OpportunityBacktestConfig,
) -> list[TradeOutcome]:
    outcomes: list[TradeOutcome] = []
    busy_until = -1
    for candidate in generate_candidates(
        bars_m5,
        bars_m15,
        config.mechanism,
    ):
        if candidate.entry_index <= busy_until:
            continue
        if active_macro_blackouts(config.macro_events, candidate.entry_at):
            continue
        outcome, exit_index, rejection = _simulate_candidate(
            bars_m5,
            candidate,
            config,
        )
        if rejection is not None or outcome is None or exit_index is None:
            continue
        outcomes.append(outcome)
        busy_until = exit_index
    return outcomes


def _window(
    outcome: TradeOutcome,
    *,
    train_end: datetime,
    validation_end: datetime,
) -> AttributionWindow | None:
    if train_end <= outcome.signal_at < validation_end:
        return AttributionWindow.VALIDATION
    if outcome.signal_at >= validation_end:
        return AttributionWindow.HOLDOUT
    return None


def build_xau_structural_displacement_regime_session_attribution(
    files_dir: Path,
    *,
    generated_at: datetime,
) -> RegimeSessionAttributionReport:
    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or not capital.is_demo:
        raise ValueError("attribution requires available MT4 DEMO equity/balance")

    specs = list_mt4_symbol_specs(files_dir)
    spec = specs.get(SYMBOL)
    if spec is None:
        raise ValueError("XAUUSD broker symbol spec not found")
    execution_model = load_research_execution_model(
        settings.research_execution_model_path
    )
    if execution_model is not None:
        spec = apply_research_execution_model(spec, execution_model)

    m5_path = resolve_mt4_history_path(files_dir, SYMBOL, Timeframe.M5)
    m15_path = resolve_mt4_history_path(files_dir, SYMBOL, Timeframe.M15)
    if m5_path is None or m15_path is None:
        raise ValueError("XAUUSD M5/M15 history not found")
    bars_m5 = read_mt4_csv(m5_path, SYMBOL, Timeframe.M5)
    bars_m15 = read_mt4_csv(m15_path, SYMBOL, Timeframe.M15)
    if not bars_m5 or not bars_m15:
        raise ValueError("XAUUSD M5/M15 history is empty")

    split = default_probe_review_split()
    config = OpportunityBacktestConfig(
        spec=spec,
        mechanism=MECHANISM,
        split=split,
        requested_risk_fraction=settings.risk_per_trade_fraction,
        capital_eur=capital.capital_eur,
        macro_events=load_macro_events(settings.macro_events_path),
    )
    outcomes = _replay_outcomes(bars_m5, bars_m15, config)
    attributed = [
        (
            outcome,
            _window(
                outcome,
                train_end=split.train_end,
                validation_end=split.validation_end,
            ),
            active_session_at(outcome.signal_at),
            _regime_at(bars_m15, outcome.signal_at),
        )
        for outcome in outcomes
    ]
    attributed = [row for row in attributed if row[1] is not None]

    session_buckets = [
        _bucket(
            window=window,
            dimension=AttributionDimension.SESSION,
            key=session,
            outcomes=[
                row[0]
                for row in attributed
                if row[1] == window and row[2] == session
            ],
        )
        for window in AttributionWindow
        for session in SESSION_PARTITION
    ]
    regime_buckets = [
        _bucket(
            window=window,
            dimension=AttributionDimension.REGIME,
            key=regime.value,
            outcomes=[
                row[0]
                for row in attributed
                if row[1] == window and row[3] == regime
            ],
        )
        for window in AttributionWindow
        for regime in REGIME_PARTITION
    ]

    validation_trades = sum(
        row.trades
        for row in session_buckets
        if row.window == AttributionWindow.VALIDATION
    )
    holdout_trades = sum(
        row.trades
        for row in session_buckets
        if row.window == AttributionWindow.HOLDOUT
    )
    return RegimeSessionAttributionReport(
        generated_at=generated_at,
        symbol=SYMBOL,
        strategy_id=f"{SYMBOL}:{MECHANISM.value}",
        target_r=1.5,
        capital_eur=capital.capital_eur,
        capital_source=capital.source.value,
        train_end=split.train_end,
        validation_end=split.validation_end,
        validation_trades=validation_trades,
        holdout_trades=holdout_trades,
        session_buckets=session_buckets,
        regime_buckets=regime_buckets,
        session_partition=list(SESSION_PARTITION),
        regime_partition=list(REGIME_PARTITION),
        authority_effect=False,
        limitations=[
            "Attribution is descriptive; no session or regime is enabled/disabled by this report.",
            "Validation and holdout remain separate; train outcomes are excluded.",
            "No session-regime cross-product or retrospective ranking is produced.",
        ],
    )

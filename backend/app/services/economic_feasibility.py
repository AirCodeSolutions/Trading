from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec, PositionSizeRequest
from app.domain.economic_feasibility import (
    AssetEconomicFeasibility,
    CausalPatternEconomicFeasibility,
    EconomicFeasibilityReport,
    StopFeasibilitySummary,
)
from app.domain.market import Timeframe
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.capital_risk import monetary_loss_per_lot, size_position
from app.services.causal_pattern_research import _historical_causal_episodes
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.trading_intelligence import _atr_series

DEFAULT_STOP_ATR_MULTIPLES = (0.50, 0.75, 1.00, 1.50)


def build_economic_feasibility_report(
    files_dir: Path,
    execution_model_path: Path,
    symbols: tuple[str, ...],
    *,
    generated_at: datetime,
    risk_fraction: float | None = None,
    capital_eur: float | None = None,
    stop_atr_multiples: tuple[float, ...] = DEFAULT_STOP_ATR_MULTIPLES,
) -> EconomicFeasibilityReport:
    if not stop_atr_multiples or any(value <= 0 for value in stop_atr_multiples):
        raise ValueError("stop_atr_multiples must all be positive")

    selected_risk = risk_fraction or settings.risk_per_trade_fraction
    selected_capital = capital_eur or settings.reference_capital_eur
    if selected_risk <= 0 or selected_risk > settings.absolute_max_risk_fraction:
        raise ValueError("risk_fraction is outside the configured policy")
    if selected_capital <= 0:
        raise ValueError("capital_eur must be positive")

    execution_model = load_research_execution_model(execution_model_path)
    live_specs = list_mt4_symbol_specs(files_dir)
    assets: list[AssetEconomicFeasibility] = []

    for symbol in symbols:
        raw_spec = live_specs.get(symbol.upper())
        if raw_spec is None:
            raise ValueError(f"broker symbol spec missing for {symbol.upper()}")
        spec = apply_research_execution_model(raw_spec, execution_model)
        assets.append(
            _analyze_asset_feasibility(
                files_dir,
                symbol.upper(),
                spec=spec,
                risk_fraction=selected_risk,
                capital_eur=selected_capital,
                stop_atr_multiples=stop_atr_multiples,
            )
        )

    return EconomicFeasibilityReport(
        generated_at=generated_at,
        reference_capital_eur=selected_capital,
        risk_fraction=selected_risk,
        max_spread_to_stop=settings.max_spread_to_stop,
        max_margin_fraction=settings.max_margin_fraction,
        stop_atr_multiples=list(stop_atr_multiples),
        assets=assets,
    )


def _analyze_asset_feasibility(
    files_dir: Path,
    symbol: str,
    *,
    spec: BrokerSymbolSpec,
    risk_fraction: float,
    capital_eur: float,
    stop_atr_multiples: tuple[float, ...],
) -> AssetEconomicFeasibility:
    bars = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    atr = _atr_series(bars)
    episodes = _historical_causal_episodes(
        bars=bars,
        atr=atr,
        move_threshold_atr=1.5,
        horizon_bars=12,
    )

    spread_floor, risk_ceiling, minimum_capital = _feasible_stop_envelope(
        spec,
        risk_fraction=risk_fraction,
        capital_eur=capital_eur,
    )
    max_margin_budget = capital_eur * settings.max_margin_fraction
    min_lot_margin = spec.margin_required * spec.min_lot
    interval = (
        spread_floor <= risk_ceiling
        and min_lot_margin <= max_margin_budget
    )

    stop_profiles = [
        _summarize_stop_profile(
            episodes,
            spec=spec,
            risk_fraction=risk_fraction,
            capital_eur=capital_eur,
            stop_atr_multiple=multiple,
        )
        for multiple in stop_atr_multiples
    ]

    grouped: dict[OpportunityCausalPattern, list[dict]] = defaultdict(list)
    for row in episodes:
        grouped[row["context"].pattern].append(row)

    causal_patterns = [
        CausalPatternEconomicFeasibility(
            pattern=pattern,
            stop_profiles=[
                _summarize_stop_profile(
                    grouped.get(pattern, []),
                    spec=spec,
                    risk_fraction=risk_fraction,
                    capital_eur=capital_eur,
                    stop_atr_multiple=multiple,
                )
                for multiple in stop_atr_multiples
            ],
        )
        for pattern in OpportunityCausalPattern
    ]

    return AssetEconomicFeasibility(
        symbol=symbol,
        frozen_spread=spec.spread,
        min_lot=spec.min_lot,
        min_lot_margin_eur=min_lot_margin,
        spread_stop_floor_price=spread_floor,
        risk_stop_ceiling_price=risk_ceiling,
        feasible_stop_interval=interval,
        minimum_reference_capital_eur=minimum_capital,
        total_episodes=len(episodes),
        stop_profiles=stop_profiles,
        causal_patterns=causal_patterns,
    )


def _feasible_stop_envelope(
    spec: BrokerSymbolSpec,
    *,
    risk_fraction: float,
    capital_eur: float | None = None,
) -> tuple[float, float, float]:
    selected_capital = capital_eur or settings.reference_capital_eur
    spread_floor = spec.spread / settings.max_spread_to_stop
    risk_budget = selected_capital * risk_fraction
    risk_ceiling = (
        risk_budget
        * spec.tick_size
        / (spec.tick_value * spec.min_lot)
    )

    min_lot_loss_at_spread_floor = (
        monetary_loss_per_lot(spec, spread_floor) * spec.min_lot
    )
    risk_required_capital = (
        min_lot_loss_at_spread_floor / risk_fraction
        if risk_fraction > 0
        else 0.0
    )
    margin_required_capital = (
        spec.margin_required * spec.min_lot / settings.max_margin_fraction
        if settings.max_margin_fraction > 0
        else 0.0
    )
    minimum_capital = max(
        risk_required_capital,
        margin_required_capital,
    )
    return spread_floor, risk_ceiling, minimum_capital


def _summarize_stop_profile(
    episodes: list[dict],
    *,
    spec: BrokerSymbolSpec,
    risk_fraction: float,
    capital_eur: float | None = None,
    stop_atr_multiple: float,
) -> StopFeasibilitySummary:
    approved_results = []
    rejected_spread = 0
    rejected_min_lot = 0
    rejected_margin = 0
    rejected_other = 0

    for row in episodes:
        stop_distance = float(row["atr_m5"]) * stop_atr_multiple
        entry = float(row["reference_price"])
        stop = entry - stop_distance
        if stop <= 0:
            rejected_other += 1
            continue

        result = size_position(
            PositionSizeRequest(
                spec=spec,
                entry=entry,
                stop=stop,
                requested_risk_fraction=risk_fraction,
                capital_eur=capital_eur,
            )
        )
        if result.approved:
            approved_results.append(result)
        elif result.reason == "spread consumes too much of the stop distance":
            rejected_spread += 1
        elif result.reason in {
            "minimum broker lot exceeds the risk budget",
            "rounded size falls below the broker minimum lot",
        }:
            rejected_min_lot += 1
        elif result.reason == "estimated margin exceeds capital policy":
            rejected_margin += 1
        else:
            rejected_other += 1

    total = len(episodes)
    approved = len(approved_results)
    return StopFeasibilitySummary(
        stop_atr_multiple=stop_atr_multiple,
        episodes=total,
        approved=approved,
        rejected_spread=rejected_spread,
        rejected_min_lot=rejected_min_lot,
        rejected_margin=rejected_margin,
        rejected_other=rejected_other,
        approval_rate=(approved / total) if total else 0.0,
        average_expected_loss_eur=(
            fmean(row.expected_loss_eur for row in approved_results)
            if approved_results
            else 0.0
        ),
        average_lots=(
            fmean(row.lots for row in approved_results)
            if approved_results
            else 0.0
        ),
    )


ECONOMIC_FEASIBILITY_FILE = "economic_feasibility_latest.json"


def write_economic_feasibility_report(
    path: Path,
    report: EconomicFeasibilityReport,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def load_economic_feasibility_report(
    path: Path,
) -> EconomicFeasibilityReport | None:
    if not path.is_file():
        return None
    try:
        return EconomicFeasibilityReport.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None

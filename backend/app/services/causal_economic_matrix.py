from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.domain.causal_economic_matrix import (
    CausalEconomicCell,
    CausalEconomicMatrixReport,
    DirectionalConsistency,
)
from app.services.causal_pattern_research import build_causal_pattern_research_report
from app.services.economic_feasibility import build_economic_feasibility_report


def build_causal_economic_matrix(
    files_dir: Path,
    execution_model_path: Path,
    symbols: tuple[str, ...],
    *,
    generated_at: datetime,
    train_end: datetime,
    validation_end: datetime,
) -> CausalEconomicMatrixReport:
    causal = build_causal_pattern_research_report(
        files_dir,
        symbols,
        generated_at=generated_at,
        train_end=train_end,
        validation_end=validation_end,
    )
    economic = build_economic_feasibility_report(
        files_dir,
        execution_model_path,
        symbols,
        generated_at=generated_at,
    )

    economic_by_symbol = {asset.symbol: asset for asset in economic.assets}
    cells: list[CausalEconomicCell] = []

    for asset in causal.assets:
        econ_asset = economic_by_symbol[asset.symbol]
        econ_patterns = {
            row.pattern: row
            for row in econ_asset.causal_patterns
        }

        for pattern in asset.patterns:
            econ_pattern = econ_patterns[pattern.pattern]
            best_profile = max(
                econ_pattern.stop_profiles,
                key=lambda row: (
                    row.approval_rate,
                    -row.stop_atr_multiple,
                ),
            )
            cells.append(
                CausalEconomicCell(
                    symbol=asset.symbol,
                    pattern=pattern.pattern,
                    directional_consistency=_directional_consistency(
                        pattern.train.alignment_rate,
                        pattern.validation.alignment_rate,
                        pattern.holdout.alignment_rate,
                    ),
                    train_alignment_rate=pattern.train.alignment_rate,
                    validation_alignment_rate=pattern.validation.alignment_rate,
                    holdout_alignment_rate=pattern.holdout.alignment_rate,
                    train_directional_episodes=pattern.train.directional_episodes,
                    validation_directional_episodes=(
                        pattern.validation.directional_episodes
                    ),
                    holdout_directional_episodes=pattern.holdout.directional_episodes,
                    asset_feasible_stop_interval=(
                        econ_asset.feasible_stop_interval
                    ),
                    best_stop_atr_multiple=(
                        best_profile.stop_atr_multiple
                        if best_profile.episodes > 0
                        else None
                    ),
                    best_approval_rate=best_profile.approval_rate,
                    minimum_reference_capital_eur=(
                        econ_asset.minimum_reference_capital_eur
                    ),
                )
            )

    return CausalEconomicMatrixReport(
        generated_at=generated_at,
        reference_capital_eur=economic.reference_capital_eur,
        cells=sorted(
            cells,
            key=lambda row: (
                row.symbol,
                row.pattern.value,
            ),
        ),
    )


def _directional_consistency(
    train_rate: float | None,
    validation_rate: float | None,
    holdout_rate: float | None,
) -> DirectionalConsistency:
    rates = (train_rate, validation_rate, holdout_rate)
    if any(rate is None for rate in rates):
        return DirectionalConsistency.INSUFFICIENT

    concrete = tuple(float(rate) for rate in rates if rate is not None)
    if all(rate > 0.5 for rate in concrete):
        return DirectionalConsistency.ALIGNED_STABLE
    if all(rate < 0.5 for rate in concrete):
        return DirectionalConsistency.OPPOSED_STABLE
    return DirectionalConsistency.MIXED

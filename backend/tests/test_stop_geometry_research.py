from datetime import UTC, datetime
from pathlib import Path

from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.stop_geometry import StopGeometryResearchReport
from app.services.stop_geometry_research import build_stop_geometry_report


def test_legacy_diagnostics_are_excluded_without_backfill(tmp_path: Path) -> None:
    legacy = ShadowOpportunityDiagnostic(
        symbol="EURUSD",
        mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        evaluated_at=datetime(2026, 9, 28, 10, tzinfo=UTC),
        latest_closed_m5_at=datetime(2026, 9, 28, 9, 55, tzinfo=UTC),
        latest_closed_m15_at=datetime(2026, 9, 28, 9, 45, tzinfo=UTC),
        state=ShadowSignalState.SIGNAL_EXECUTABLE,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=0.001,
        atr_ratio=1,
        volatility_percentile=0.5,
        efficiency=0.5,
        reason="test",
    ).model_dump_json()
    (tmp_path / "EURUSD_failed_auction.jsonl").write_text(legacy + "\n", encoding="utf-8")

    report = build_stop_geometry_report(
        tmp_path,
        now=datetime(2026, 9, 28, 11, tzinfo=UTC),
        window_hours=168,
        symbols=("EURUSD",),
    )

    assert isinstance(report, StopGeometryResearchReport)
    assert report.instrumented_observations == 0
    assert report.legacy_observations_excluded == 1
    assert report.summaries == []

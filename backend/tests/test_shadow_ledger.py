from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.services.shadow_ledger import append_shadow_observation

TZ = ZoneInfo("Europe/Athens")


def diagnostic(at: datetime) -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        evaluated_at=at,
        latest_closed_m5_at=at,
        latest_closed_m15_at=at,
        state=ShadowSignalState.NO_SIGNAL,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=100,
        atr_ratio=1,
        volatility_percentile=0.5,
        efficiency=0.3,
        reason="test",
    )


def test_shadow_ledger_deduplicates_same_m5_close(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    at = datetime(2026, 9, 19, 13, 0, tzinfo=TZ)

    assert append_shadow_observation(path, diagnostic(at)) is True
    assert append_shadow_observation(path, diagnostic(at)) is False
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1

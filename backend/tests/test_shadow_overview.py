from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.services.shadow_overview import load_shadow_overview

AT = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def diagnostic(
    symbol: str,
    mechanism: OpportunityMechanism,
    *,
    at: datetime,
    state: ShadowSignalState = ShadowSignalState.NO_SIGNAL,
) -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol=symbol,
        mechanism=mechanism,
        evaluated_at=at,
        latest_closed_m5_at=at - timedelta(minutes=5),
        latest_closed_m15_at=at - timedelta(minutes=15),
        state=state,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=1,
        atr_ratio=1,
        volatility_percentile=0.5,
        efficiency=0.4,
        reason="test",
    )


def test_shadow_overview_keeps_latest_observation_per_ledger(
    tmp_path: Path,
) -> None:
    path = tmp_path / "EURUSD_directional_transition.jsonl"
    old = diagnostic(
        "EURUSD",
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
        at=AT,
    )
    new = diagnostic(
        "EURUSD",
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
        at=AT + timedelta(minutes=5),
        state=ShadowSignalState.SIGNAL_BLOCKED,
    )
    path.write_text(
        old.model_dump_json() + "\n" + "{bad json}\n" + new.model_dump_json() + "\n",
        encoding="utf-8",
    )

    rows = load_shadow_overview(tmp_path)

    assert len(rows) == 1
    assert rows[0].evaluated_at == new.evaluated_at
    assert rows[0].state == ShadowSignalState.SIGNAL_BLOCKED


def test_shadow_overview_filters_symbols_and_ignores_non_diagnostic_ledgers(
    tmp_path: Path,
) -> None:
    eur = diagnostic(
        "EURUSD",
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        at=AT,
    )
    btc = diagnostic(
        "BTCUSD",
        OpportunityMechanism.POST_SHOCK_CONTINUATION,
        at=AT,
    )
    (tmp_path / "EURUSD_break_retest.jsonl").write_text(
        eur.model_dump_json() + "\n",
        encoding="utf-8",
    )
    (tmp_path / "BTCUSD_post_shock.jsonl").write_text(
        btc.model_dump_json() + "\n",
        encoding="utf-8",
    )
    (tmp_path / "execution_costs.jsonl").write_text("{}\n", encoding="utf-8")

    rows = load_shadow_overview(tmp_path, symbols=("EURUSD",))

    assert [row.symbol for row in rows] == ["EURUSD"]

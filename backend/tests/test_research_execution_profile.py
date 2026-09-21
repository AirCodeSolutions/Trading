import json

import pytest
from pathlib import Path

from app.domain.broker import BrokerSymbolSpec
from app.services.research_execution_profile import (
    apply_research_execution_profile,
    load_research_execution_profile,
)


def live_spec(*, spread: float) -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="GBPUSD",
        bid=1.3380,
        ask=1.3380 + spread,
        tick_size=0.00001,
        tick_value=0.90,
        min_lot=0.01,
        max_lot=10000,
        lot_step=0.01,
        margin_required=120,
    )


def write_profile(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "observed_through": "2026-09-21T12:00:00+03:00",
                "source": "test",
                "symbols": {
                    "GBPUSD": {
                        "spread": 0.00011,
                        "tick_size": 0.00001,
                        "tick_value": 0.87114085,
                        "min_lot": 0.01,
                        "max_lot": 10000,
                        "lot_step": 0.01,
                        "margin_required": 116.59,
                        "spread_observations": 100,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_research_profile_ignores_transient_live_spread(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    write_profile(path)
    profile = load_research_execution_profile(path)

    narrow = apply_research_execution_profile(
        live_spec(spread=0.00010),
        profile,
    )
    wide = apply_research_execution_profile(
        live_spec(spread=0.00040),
        profile,
    )

    assert narrow.spread == wide.spread
    assert narrow.spread == pytest.approx(0.00011)
    assert narrow.tick_value == wide.tick_value == 0.87114085
    assert narrow.margin_required == wide.margin_required == 116.59


def test_research_profile_preserves_live_mid_reference_only(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    write_profile(path)
    profile = load_research_execution_profile(path)
    spec = live_spec(spread=0.00030).model_copy(update={"bid": 1.4000, "ask": 1.4003})

    frozen = apply_research_execution_profile(spec, profile)

    assert frozen.bid == 1.4000
    assert frozen.ask == 1.40011
    assert frozen.spread == pytest.approx(0.00011)

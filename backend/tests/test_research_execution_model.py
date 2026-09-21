import json
from pathlib import Path

import pytest

from app.domain.broker import BrokerSymbolSpec
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)


def spec(ask: float) -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="GBPUSD",
        bid=1.33800,
        ask=ask,
        tick_size=0.00001,
        tick_value=0.75,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        margin_required=100.0,
    )


def write_model(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "test_v1",
                "as_of": "2026-09-21T14:29:00+03:00",
                "method": "frozen median",
                "symbols": {
                    "GBPUSD": {
                        "spread": 0.00011,
                        "samples": 1000,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_frozen_research_spread_does_not_depend_on_live_ask(
    tmp_path: Path,
) -> None:
    path = tmp_path / "model.json"
    write_model(path)
    model = load_research_execution_model(path)

    tight = apply_research_execution_model(spec(1.33810), model)
    wide = apply_research_execution_model(spec(1.33840), model)

    assert tight.spread == pytest.approx(0.00011)
    assert wide.spread == pytest.approx(0.00011)
    assert tight.bid == wide.bid == 1.33800
    assert tight.ask == pytest.approx(1.33811)
    assert wide.ask == pytest.approx(1.33811)


def test_missing_research_spread_proxy_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "model.json"
    write_model(path)
    model = load_research_execution_model(path)
    btc = spec(1.33810).model_copy(
        update={
            "symbol": "BTCUSD",
            "bid": 84000.0,
            "ask": 84024.5,
        }
    )

    with pytest.raises(ValueError, match="research spread proxy missing"):
        apply_research_execution_model(btc, model)

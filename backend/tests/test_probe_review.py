from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.domain.opportunity import ResearchSplit
from app.services.probe_review import _parse_strategy_id, build_probe_review_pack

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 23, 16, 0, tzinfo=TZ)
SPLIT = ResearchSplit(
    train_end=datetime(2026, 7, 1, tzinfo=TZ),
    validation_end=datetime(2026, 9, 1, tzinfo=TZ),
)


def test_probe_review_pack_refuses_strategy_without_supports_review(
    tmp_path: Path,
) -> None:
    pack = build_probe_review_pack(
        tmp_path,
        tmp_path,
        strategy_id="BTCUSD:directional_transition",
        now=NOW,
        split=SPLIT,
    )

    assert pack.review_ready is False
    assert pack.probe_qualification is None
    assert pack.historical_admission is None
    assert "not SUPPORTS_REVIEW" in pack.reason
    assert pack.requires_human_decision is True


def test_probe_review_strategy_id_parser_is_strict() -> None:
    symbol, mechanism = _parse_strategy_id("xauusd:failed_auction_reversal")
    assert symbol == "XAUUSD"
    assert mechanism.value == "failed_auction_reversal"

    with pytest.raises(ValueError, match="SYMBOL:mechanism"):
        _parse_strategy_id("bad")

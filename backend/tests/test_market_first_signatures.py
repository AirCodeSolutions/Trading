from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.services.market_first_signatures import (
    build_market_first_signature_rows,
    summarize_signature_rows,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 6, 1, 0, 0, tzinfo=TZ)


def bar(index: int, close: float) -> MarketBar:
    at = START + timedelta(minutes=5 * index)
    return MarketBar(
        symbol="BTCUSD",
        timeframe=Timeframe.M5,
        timestamp=at,
        open=close - 1,
        high=close + 2,
        low=close - 2,
        close=close,
    )


def test_signature_rows_use_only_past_features_and_future_for_denominator() -> None:
    bars = [bar(i, 100 + 0.1 * i) for i in range(100)]
    # Create a future move large enough after index 50.
    for i in range(51, 63):
        bars[i] = bar(i, 110 + i)

    rows = build_market_first_signature_rows(
        bars,
        move_threshold_atr=1.5,
        horizon_bars=12,
    )

    assert rows
    row = rows[0]
    assert row["birth_at"] <= bars[-1].timestamp + timedelta(minutes=5)
    assert "aligned_position_24" in row
    assert "compression_6_24" in row
    assert "atr_ratio_96" in row


def test_signature_summary_exposes_fixed_archetypes() -> None:
    rows = [
        {
            "birth_at": START,
            "direction": 1,
            "move_atr": 2.0,
            "aligned_return_3_atr": 0.7,
            "aligned_return_6_atr": 1.2,
            "aligned_return_12_atr": 1.5,
            "aligned_position_24": 0.9,
            "aligned_position_48": 0.8,
            "compression_6_24": 0.3,
            "atr_ratio_96": 1.3,
            "body_alignment": 0.6,
            "hour_athens": 10,
        }
    ]

    summary = summarize_signature_rows(rows)

    assert summary["episodes"] == 1
    assert summary["archetypes"]["continuation_extreme"]["count"] == 1
    assert summary["archetypes"]["compressed"]["count"] == 1
    assert summary["archetypes"]["high_volatility"]["count"] == 1

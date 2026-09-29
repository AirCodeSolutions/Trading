from app.services.market_brief import format_time_until


def test_market_brief_time_formatting() -> None:
    assert format_time_until(25) == "25 min"
    assert format_time_until(90) == "1 h 30"
    assert format_time_until(26 * 60) == "1 j 2 h"
    assert format_time_until(3 * 24 * 60 + 4 * 60) == "3 j 4 h"

from collections.abc import Sequence
from datetime import timedelta

from app.domain.market import MarketBar


SESSION_GAP_THRESHOLD = timedelta(minutes=20)
SESSION_REOPEN_WARMUP_BARS = 3


def reopen_warmup_remaining(
    bars: Sequence[MarketBar],
    index: int | None = None,
) -> int:
    if not bars:
        return 0

    current_index = len(bars) - 1 if index is None else index
    if current_index <= 0 or current_index >= len(bars):
        return 0

    first_index = max(1, current_index - SESSION_REOPEN_WARMUP_BARS + 1)
    for gap_index in range(current_index, first_index - 1, -1):
        gap = bars[gap_index].timestamp - bars[gap_index - 1].timestamp
        if gap > SESSION_GAP_THRESHOLD:
            bars_since_reopen = current_index - gap_index + 1
            return max(0, SESSION_REOPEN_WARMUP_BARS - bars_since_reopen)

    return 0

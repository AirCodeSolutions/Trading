from collections import deque
from collections.abc import Iterable

from app.domain.market import MarketBar
from app.domain.regime import RegimeSnapshot
from app.services.regime import classify_regime


class RegimeReplay:
    """One causal code path for historical replay and incremental runtime use."""

    def __init__(self, max_history: int = 250) -> None:
        if max_history < 50:
            raise ValueError("max_history must be >= 50")
        self._history: deque[MarketBar] = deque(maxlen=max_history)

    def push(self, bar: MarketBar) -> RegimeSnapshot:
        if self._history and bar.timestamp <= self._history[-1].timestamp:
            raise ValueError("replay bars must be strictly chronological")
        self._history.append(bar)
        return classify_regime(tuple(self._history))

    def replay(self, bars: Iterable[MarketBar]) -> list[RegimeSnapshot]:
        return [self.push(bar) for bar in bars]

from collections import defaultdict, deque

from app.domain.market import MarketBar, Timeframe


class MarketStore:
    def __init__(self, max_bars_per_stream: int = 2_000) -> None:
        self._bars: dict[tuple[str, Timeframe], deque[MarketBar]] = defaultdict(
            lambda: deque(maxlen=max_bars_per_stream)
        )

    def append(self, bar: MarketBar) -> None:
        key = (bar.symbol.upper(), bar.timeframe)
        stream = self._bars[key]
        if stream and bar.timestamp <= stream[-1].timestamp:
            raise ValueError("bars must arrive in strictly increasing timestamp order")
        stream.append(bar)

    def latest(self, symbol: str, timeframe: Timeframe) -> MarketBar | None:
        stream = self._bars.get((symbol.upper(), timeframe))
        return stream[-1] if stream else None

    def count(self, symbol: str, timeframe: Timeframe) -> int:
        stream = self._bars.get((symbol.upper(), timeframe))
        return len(stream) if stream else 0

from typing import Protocol, Sequence

from app.domain.market import MarketBar, Timeframe
from app.domain.trading import RiskDecision, TradeDecision


class Strategy(Protocol):
    strategy_id: str

    def evaluate(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        bars: Sequence[MarketBar],
    ) -> TradeDecision:
        ...


class RiskEngine(Protocol):
    def evaluate(self, decision: TradeDecision) -> RiskDecision:
        ...


class ExecutionBroker(Protocol):
    def submit(self, decision: TradeDecision, risk: RiskDecision) -> str:
        """Submit an approved canonical decision and return the broker order id."""
        ...

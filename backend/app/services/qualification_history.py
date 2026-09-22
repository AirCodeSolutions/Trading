from __future__ import annotations

from pathlib import Path

from app.domain.portfolio import TradingOverview
from app.domain.qualification_history import QualificationHistoryEvent


def record_qualification_history(
    path: Path,
    overview: TradingOverview,
    *,
    at,
) -> list[QualificationHistoryEvent]:
    existing = load_qualification_history(path)
    latest = {event.strategy_id: event for event in existing}
    appended: list[QualificationHistoryEvent] = []
    for item in overview.qualifications:
        previous = latest.get(item.strategy_id)
        if (
            previous is not None
            and previous.state == item.state
            and previous.closed_trades == item.closed_trades
            and previous.expectancy_r == item.expectancy_r
            and previous.profit_factor == item.profit_factor
            and previous.max_drawdown_r == item.max_drawdown_r
        ):
            continue
        event = QualificationHistoryEvent(
            at=at,
            strategy_id=item.strategy_id,
            state=item.state,
            closed_trades=item.closed_trades,
            expectancy_r=item.expectancy_r,
            profit_factor=item.profit_factor,
            max_drawdown_r=item.max_drawdown_r,
            reason=item.reason,
        )
        _append(path,event)
        latest[item.strategy_id]=event
        appended.append(event)
    return appended


def load_qualification_history(path: Path) -> list[QualificationHistoryEvent]:
    if not path.is_file():
        return []
    rows=[]
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(QualificationHistoryEvent.model_validate_json(line))
            except ValueError:
                continue
    return rows


def _append(path: Path,event: QualificationHistoryEvent)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as handle:
        handle.write(event.model_dump_json())
        handle.write("\n")

from pydantic import BaseModel, Field


class DemoCollectionState(BaseModel):
    paper_trade_id: str | None = None
    strategy_id: str | None = None
    open_command_id: str | None = None
    ticket: int | None = Field(default=None, gt=0)
    close_command_id: str | None = None
    last_completed_trade_id: str | None = None
    completed_trade_ids: list[str] = Field(default_factory=list)
    last_error: str | None = None

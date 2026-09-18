from datetime import datetime, timezone

import pytest

from app.domain.approval import (
    DecisionMode,
    ExecutionProposalRequest,
    ProposalStatus,
)
from app.domain.market import Timeframe
from app.domain.trading import Side
from app.services.approval_gate import ApprovalGate


def request() -> ExecutionProposalRequest:
    return ExecutionProposalRequest(
        symbol="EURUSD",
        timeframe=Timeframe.M5,
        side=Side.BUY,
        strategy_id="qualified_strategy",
        at=datetime(2026, 9, 18, tzinfo=timezone.utc),
        reason="test decision",
    )


def test_confirm_mode_requires_human_approval() -> None:
    gate = ApprovalGate(DecisionMode.CONFIRM)
    proposal = gate.create(request())
    assert proposal.status == ProposalStatus.PENDING_APPROVAL

    approved = gate.approve(proposal.id)
    assert approved.status == ProposalStatus.AUTHORIZED


def test_auto_mode_authorizes_without_human_click() -> None:
    gate = ApprovalGate(DecisionMode.AUTO)
    proposal = gate.create(request())
    assert proposal.status == ProposalStatus.AUTHORIZED

    with pytest.raises(ValueError):
        gate.approve(proposal.id)

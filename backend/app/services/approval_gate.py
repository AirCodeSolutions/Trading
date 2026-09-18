from uuid import uuid4

from app.domain.approval import (
    DecisionMode,
    ExecutionProposal,
    ExecutionProposalRequest,
    ProposalStatus,
)


class ApprovalGate:
    def __init__(self, mode: DecisionMode) -> None:
        self.mode = mode
        self._proposals: dict[str, ExecutionProposal] = {}

    def create(self, request: ExecutionProposalRequest) -> ExecutionProposal:
        status = (
            ProposalStatus.AUTHORIZED
            if self.mode == DecisionMode.AUTO
            else ProposalStatus.PENDING_APPROVAL
        )
        proposal = ExecutionProposal(
            id=uuid4().hex,
            status=status,
            **request.model_dump(),
        )
        self._proposals[proposal.id] = proposal
        return proposal

    def get(self, proposal_id: str) -> ExecutionProposal | None:
        return self._proposals.get(proposal_id)

    def approve(self, proposal_id: str) -> ExecutionProposal:
        proposal = self._require_pending(proposal_id)
        updated = proposal.model_copy(update={"status": ProposalStatus.AUTHORIZED})
        self._proposals[proposal_id] = updated
        return updated

    def decline(self, proposal_id: str) -> ExecutionProposal:
        proposal = self._require_pending(proposal_id)
        updated = proposal.model_copy(update={"status": ProposalStatus.DECLINED})
        self._proposals[proposal_id] = updated
        return updated

    def _require_pending(self, proposal_id: str) -> ExecutionProposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise KeyError("proposal not found")
        if proposal.status != ProposalStatus.PENDING_APPROVAL:
            raise ValueError("proposal is not pending approval")
        return proposal

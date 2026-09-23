from datetime import datetime
from pathlib import Path

from app.domain.opportunity import (
    OpportunityMechanism,
    PortfolioResearchRequest,
    ResearchSplit,
)
from app.domain.probe_review import ProbeReviewPack
from app.services.opportunity_funnel import build_opportunity_funnel
from app.services.opportunity_matrix import run_mt4_portfolio_research


def build_probe_review_pack(
    files_dir: Path,
    runtime_dir: Path,
    *,
    strategy_id: str,
    now: datetime,
    split: ResearchSplit,
    macro_events_path: Path | None = None,
    research_execution_model_path: Path | None = None,
) -> ProbeReviewPack:
    symbol, mechanism = _parse_strategy_id(strategy_id)
    funnel = build_opportunity_funnel(
        runtime_dir,
        now=now,
        window_hours=24,
        symbols=(symbol,),
    )
    queue_item = next(
        (
            row
            for row in funnel.unqualified_probe_review_queue
            if row.strategy_id == strategy_id
        ),
        None,
    )
    if queue_item is None:
        return ProbeReviewPack(
            strategy_id=strategy_id,
            review_ready=False,
            reason=(
                "strategy is not SUPPORTS_REVIEW; no historical replay was run "
                "and no admission change is allowed"
            ),
        )

    result = run_mt4_portfolio_research(
        files_dir,
        PortfolioResearchRequest(
            split=split,
            symbols=[symbol],
            mechanisms=[mechanism],
        ),
        macro_events_path=macro_events_path,
        research_execution_model_path=research_execution_model_path,
    )
    replay = next(
        (
            row
            for row in result.results
            if row.symbol == symbol and row.mechanism == mechanism
        ),
        None,
    )
    if replay is None:
        return ProbeReviewPack(
            strategy_id=strategy_id,
            review_ready=True,
            reason="SUPPORTS_REVIEW but dedicated historical replay could not be built",
            probe_qualification=queue_item.qualification,
        )

    return ProbeReviewPack(
        strategy_id=strategy_id,
        review_ready=True,
        reason=(
            "prospective executable probes support dedicated review; "
            "historical replay is attached but cannot change admission automatically"
        ),
        probe_qualification=queue_item.qualification,
        historical_admission=replay.admission,
        train=replay.train,
        validation=replay.validation,
        holdout=replay.holdout,
    )


def _parse_strategy_id(strategy_id: str) -> tuple[str, OpportunityMechanism]:
    try:
        symbol, mechanism_raw = strategy_id.split(":", 1)
        mechanism = OpportunityMechanism(mechanism_raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("strategy_id must be SYMBOL:mechanism") from exc
    symbol = symbol.upper().strip()
    if not symbol or not symbol.isalnum():
        raise ValueError("strategy_id symbol is invalid")
    return symbol, mechanism

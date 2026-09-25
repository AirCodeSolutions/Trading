from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import (
    OpportunityMechanism,
    PortfolioResearchRequest,
    ResearchSplit,
)
from app.domain.probe_review import ProbeReviewContract, ProbeReviewPack
from app.domain.trading_intelligence import TradingIntelligenceOverview
from app.services.opportunity_funnel import build_opportunity_funnel
from app.services.opportunity_matrix import run_mt4_portfolio_research
from app.services.trading_intelligence import build_trading_intelligence

REVIEW_EVIDENCE_WINDOW_HOURS = 168
REVIEW_TIMEZONE = "Europe/Athens"
REVIEW_TRAIN_END_LOCAL = "2026-07-01T00:00:00"
REVIEW_VALIDATION_END_LOCAL = "2026-09-01T00:00:00"


def default_probe_review_contract() -> ProbeReviewContract:
    timezone = ZoneInfo(REVIEW_TIMEZONE)
    return ProbeReviewContract(
        train_end=datetime.fromisoformat(REVIEW_TRAIN_END_LOCAL).replace(
            tzinfo=timezone
        ),
        validation_end=datetime.fromisoformat(REVIEW_VALIDATION_END_LOCAL).replace(
            tzinfo=timezone
        ),
        timezone=REVIEW_TIMEZONE,
        evidence_window_hours=REVIEW_EVIDENCE_WINDOW_HOURS,
    )


def default_probe_review_split() -> ResearchSplit:
    contract = default_probe_review_contract()
    return ResearchSplit(
        train_end=contract.train_end,
        validation_end=contract.validation_end,
    )


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

    intelligence = build_trading_intelligence(
        files_dir,
        runtime_dir,
        now=now,
        window_hours=REVIEW_EVIDENCE_WINDOW_HOURS,
        symbols=(symbol,),
        include_waiting_early_context=True,
    )
    evidence_fields = _review_evidence_fields(intelligence, strategy_id)

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
            **evidence_fields,
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
        **evidence_fields,
    )


def _review_evidence_fields(
    intelligence: TradingIntelligenceOverview,
    strategy_id: str,
) -> dict[str, object]:
    probe_context = (
        next(
            (
                row
                for row in intelligence.probe_early_context.summaries
                if row.strategy_id == strategy_id
            ),
            None,
        )
        if intelligence.probe_early_context is not None
        else None
    )
    waiting_cost = next(
        (
            row
            for row in intelligence.waiting_costs
            if row.strategy_id == strategy_id
        ),
        None,
    )
    waiting_early = (
        next(
            (
                row
                for row in intelligence.waiting_early_context.summaries
                if row.strategy_id == strategy_id
            ),
            None,
        )
        if intelligence.waiting_early_context is not None
        else None
    )
    admitted_context = (
        next(
            (
                row
                for row in intelligence.admitted_trade_early_context.summaries
                if row.strategy_id == strategy_id
            ),
            None,
        )
        if intelligence.admitted_trade_early_context is not None
        else None
    )
    blocked_contexts = (
        [
            row
            for row in intelligence.blocked_probe_early_context.summaries
            if row.strategy_id == strategy_id
        ]
        if intelligence.blocked_probe_early_context is not None
        else []
    )
    return {
        "evidence_window_hours": REVIEW_EVIDENCE_WINDOW_HOURS,
        "prospective_probe_context": probe_context,
        "waiting_cost_context": waiting_cost,
        "waiting_early_context": waiting_early,
        "admitted_trade_context": admitted_context,
        "blocked_probe_contexts": blocked_contexts,
    }


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

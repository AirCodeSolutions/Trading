from pathlib import Path

from app.core.config import settings
from app.domain.opportunity import PortfolioResearchRequest, PortfolioResearchResult
from app.domain.strategy_universe import ACTIVE_ASSETS
from app.services.opportunity_matrix import run_mt4_portfolio_research
from app.services.probe_review import default_probe_review_split
from app.services.runtime_admission_registry import save_research_admissions
from app.services.runtime_capital import resolve_demo_sizing_capital


def refresh_runtime_admissions(
    files_dir: Path,
    runtime_dir: Path,
) -> PortfolioResearchResult:
    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or not capital.is_demo:
        raise ValueError(
            "runtime admission refresh requires available MT4 DEMO equity/balance"
        )

    request = PortfolioResearchRequest(
        split=default_probe_review_split(),
        symbols=list(ACTIVE_ASSETS),
        capital_eur=capital.capital_eur,
        requested_risk_fraction=settings.risk_per_trade_fraction,
    )
    result = run_mt4_portfolio_research(
        files_dir,
        request,
        macro_events_path=settings.macro_events_path,
        research_execution_model_path=settings.research_execution_model_path,
    )
    save_research_admissions(
        runtime_dir / "strategy_admissions.json",
        result,
    )
    return result

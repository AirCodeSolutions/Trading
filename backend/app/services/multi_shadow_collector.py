from datetime import datetime
from pathlib import Path

from app.domain.market import Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowCollectionResult
from app.services.market_universe import build_market_universe
from app.services.mt4_market_data import load_closed_market_bars
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.shadow_ledger import append_shadow_observation
from app.services.shadow_paper import advance_shadow_paper_book
from app.services.shadow_scanner import scan_shadow_opportunity

_MECHANISM_SLUG = {
    OpportunityMechanism.BREAK_RETEST_REACCEL: "break_retest",
    OpportunityMechanism.FAILED_AUCTION_REVERSAL: "failed_auction",
    OpportunityMechanism.POST_SHOCK_CONTINUATION: "post_shock",
}


def collect_all_shadow_once(
    files_dir: Path,
    runtime_dir: Path,
    evaluated_at: datetime,
) -> list[ShadowCollectionResult]:
    results: list[ShadowCollectionResult] = []
    assets = [
        asset
        for asset in build_market_universe(files_dir, evaluated_at)
        if asset.paper_ready and asset.quote_live
    ]

    for asset in assets:
        spec = get_mt4_symbol_spec(files_dir, asset.symbol)
        if spec is None:
            continue
        bars_m5 = load_closed_market_bars(
            files_dir,
            asset.symbol,
            timeframe=Timeframe.M5,
            evaluated_at=evaluated_at,
        )
        bars_m15 = load_closed_market_bars(
            files_dir,
            asset.symbol,
            timeframe=Timeframe.M15,
            evaluated_at=evaluated_at,
        )
        if len(bars_m5) < 30 or len(bars_m15) < 50:
            continue

        for mechanism in OpportunityMechanism:
            diagnostic = scan_shadow_opportunity(
                bars_m5,
                bars_m15,
                spec,
                mechanism,
                evaluated_at,
            )
            slug = _MECHANISM_SLUG[mechanism]
            prefix = f"{asset.symbol}_{slug}"
            ledger_path = runtime_dir / f"{prefix}.jsonl"
            appended = append_shadow_observation(ledger_path, diagnostic)
            paper = advance_shadow_paper_book(
                diagnostic=diagnostic,
                spec=spec,
                bars_m5=bars_m5,
                state_path=runtime_dir / f"{prefix}_paper_state.json",
                trades_path=runtime_dir / f"{prefix}_paper_trades.jsonl",
                evaluated_at=evaluated_at,
            )
            results.append(
                ShadowCollectionResult(
                    appended=appended,
                    ledger_path=str(ledger_path),
                    diagnostic=diagnostic,
                    paper=paper,
                )
            )

    return results


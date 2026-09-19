from datetime import datetime
from pathlib import Path

from app.domain.market import Timeframe
from app.domain.shadow import ShadowCollectionResult
from app.services.btc_break_retest_shadow import scan_btc_break_retest_shadow
from app.services.mt4_live_bars import read_closed_bar_snapshot
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.shadow_ledger import append_shadow_observation
from app.services.shadow_paper import advance_shadow_paper_book


def collect_btc_break_retest_once(
    files_dir: Path,
    ledger_path: Path,
    evaluated_at: datetime,
) -> ShadowCollectionResult:
    spec = get_mt4_symbol_spec(files_dir, "BTCUSD")
    if spec is None:
        raise FileNotFoundError("BTCUSD broker symbol spec not found")

    m5_path = files_dir / "mt4_bars_BTCUSD_M5.json"
    m15_path = files_dir / "mt4_bars_BTCUSD_M15.json"
    if not m5_path.is_file() or not m15_path.is_file():
        raise FileNotFoundError("BTCUSD closed-bar snapshots not found")

    bars_m5 = read_closed_bar_snapshot(m5_path, "BTCUSD", Timeframe.M5)
    bars_m15 = read_closed_bar_snapshot(m15_path, "BTCUSD", Timeframe.M15)
    diagnostic = scan_btc_break_retest_shadow(
        bars_m5,
        bars_m15,
        spec,
        evaluated_at,
    )
    appended = append_shadow_observation(ledger_path, diagnostic)

    state_path = ledger_path.parent / "BTCUSD_break_retest_paper_state.json"
    trades_path = ledger_path.parent / "BTCUSD_break_retest_paper_trades.jsonl"
    paper = advance_shadow_paper_book(
        diagnostic=diagnostic,
        spec=spec,
        bars_m5=bars_m5,
        state_path=state_path,
        trades_path=trades_path,
        evaluated_at=evaluated_at,
    )

    return ShadowCollectionResult(
        appended=appended,
        ledger_path=str(ledger_path),
        diagnostic=diagnostic,
        paper=paper,
    )

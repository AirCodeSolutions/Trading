import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.portfolio_overview import build_trading_overview

TZ = ZoneInfo("Europe/Athens")


def test_overview_keeps_demo_balance_separate_from_200_eur_reference(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    (files_dir / "mt4_data_BTCUSD.json").write_text(
        json.dumps(
            {
                "account": {
                    "is_demo": "1",
                    "balance": "873900",
                    "equity": "873800",
                    "margin": "100",
                    "freeMargin": "873700",
                    "account_number": "must-not-leak",
                },
                "positions": {},
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(
        files_dir,
        runtime_dir,
        datetime(2026, 9, 19, 17, 0, tzinfo=TZ),
    )

    assert overview.broker is not None
    assert overview.broker.balance == 873900
    assert overview.risk.reference_capital_eur == 200
    assert overview.portfolio.action == "no_trade"
    assert overview.qualifications == []
    assert overview.paper_strategies == []

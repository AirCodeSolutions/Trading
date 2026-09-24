import json
from pathlib import Path

from app.services.runtime_capital import resolve_demo_sizing_capital


def test_runtime_capital_uses_demo_equity_before_balance(tmp_path: Path) -> None:
    (tmp_path / "mt4_data_XAUUSD.json").write_text(
        json.dumps(
            {
                "account": {
                    "is_demo": "1",
                    "balance": "873900.00",
                    "equity": "873859.85",
                    "margin": "0",
                    "freeMargin": "873859.85",
                },
                "positions": {},
            }
        ),
        encoding="utf-8",
    )

    result = resolve_demo_sizing_capital(tmp_path)

    assert result.capital_eur == 873859.85
    assert result.source == "broker_equity"
    assert result.is_demo is True


def test_runtime_capital_falls_back_to_balance_when_equity_is_zero(
    tmp_path: Path,
) -> None:
    (tmp_path / "mt4_data_BTCUSD.json").write_text(
        json.dumps(
            {
                "account": {
                    "is_demo": "1",
                    "balance": "850000",
                    "equity": "0",
                    "margin": "0",
                    "freeMargin": "850000",
                },
                "positions": {},
            }
        ),
        encoding="utf-8",
    )

    result = resolve_demo_sizing_capital(tmp_path)

    assert result.capital_eur == 850000
    assert result.source == "broker_balance"


def test_runtime_capital_refuses_non_demo_account(tmp_path: Path) -> None:
    (tmp_path / "mt4_data_XAUUSD.json").write_text(
        json.dumps(
            {
                "account": {
                    "is_demo": "0",
                    "balance": "100000",
                    "equity": "100000",
                    "margin": "0",
                    "freeMargin": "100000",
                },
                "positions": {},
            }
        ),
        encoding="utf-8",
    )

    result = resolve_demo_sizing_capital(tmp_path)

    assert result.capital_eur is None
    assert result.source == "unavailable"
    assert result.is_demo is False

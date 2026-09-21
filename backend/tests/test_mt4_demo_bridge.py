from pathlib import Path


def test_demo_bridge_is_magic_scoped_and_supports_explicit_close_commands() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "mt4" / "TradingDemoExecutionBridge.mq4").read_text(encoding="utf-8")

    assert 'string CLOSE_COMMAND_FILE = "trading_demo_close_command.csv";' in source
    assert "ProcessCloseCommand();" in source
    assert "OrderMagicNumber() != MagicNumber" in source
    assert "OrderClose(" in source

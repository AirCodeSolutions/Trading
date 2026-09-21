from pathlib import Path


def test_demo_bridge_is_magic_scoped_and_supports_explicit_close_commands() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "mt4" / "TradingDemoExecutionBridge.mq4").read_text(encoding="utf-8")

    assert "input bool AllowDemoExecution = true;" in source
    assert 'string CLOSE_COMMAND_FILE = "trading_demo_close_command.csv";' in source
    assert "ProcessCloseCommand();" in source
    assert "OrderMagicNumber() != MagicNumber" in source
    assert "OrderClose(" in source


def test_demo_bridge_routes_commands_to_chart_symbol_and_serializes_execution() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "mt4" / "TradingDemoExecutionBridge.mq4").read_text(encoding="utf-8")

    assert 'string EXECUTION_LOCK_FILE = "trading_demo_execution.lock";' in source
    assert "int AcquireExecutionLock()" in source
    assert "if(symbol != Symbol())" in source
    assert "if(OrderSymbol() != Symbol())" in source
    assert "FileClose(lockHandle);" in source

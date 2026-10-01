from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.broker import BrokerSymbolSpec
from app.domain.economic_contract import (
    EconomicChangeAxis,
    EconomicContract,
    EconomicContractRole,
    EconomicVariantMetrics,
    PairedEconomicComparison,
    PairedEconomicContractReport,
)
from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import ShadowPaperState, ShadowPaperTrade
from app.domain.trading import Side
from app.services.shadow_paper import (
    append_closed_trade,
    create_paper_trade,
    load_closed_trades,
    load_shadow_paper_state,
    resolve_open_trade,
    save_shadow_paper_state,
)

PAIR_COMPARISON_ID = "xau_structural_displacement_target_1r_vs_1_5r"

XAU_SD_CHAMPION_1R = EconomicContract(
    contract_id="xau_sd_target_1r_v1",
    version=1,
    symbol="XAUUSD",
    mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    role=EconomicContractRole.CHAMPION,
    change_axis=EconomicChangeAxis.TARGET_R,
    target_r=1.0,
    max_holding_bars=12,
    description="XAU structural displacement champion fixed target 1.0R",
)

XAU_SD_CHALLENGER_1_5R = EconomicContract(
    contract_id="xau_sd_target_1_5r_v2",
    version=2,
    symbol="XAUUSD",
    mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    role=EconomicContractRole.CHALLENGER,
    change_axis=EconomicChangeAxis.TARGET_R,
    target_r=1.5,
    max_holding_bars=12,
    description="XAU structural displacement challenger fixed target 1.5R",
)

XAU_SD_TARGET_CONTRACTS = (
    XAU_SD_CHAMPION_1R,
    XAU_SD_CHALLENGER_1_5R,
)
def _prefix(contract: EconomicContract) -> str:
    return f"{contract.symbol}_{contract.mechanism.value}_{contract.contract_id}"


def _state_path(runtime_dir: Path, contract: EconomicContract) -> Path:
    return runtime_dir / f"{_prefix(contract)}_paired_state.json"


def _trades_path(runtime_dir: Path, contract: EconomicContract) -> Path:
    return runtime_dir / f"{_prefix(contract)}_paired_trades.jsonl"


def _target_price(
    trade: ShadowPaperTrade,
    target_r: float,
) -> float:
    if trade.side == Side.BUY:
        return trade.entry_price + target_r * trade.risk_distance
    return trade.entry_price - target_r * trade.risk_distance


def _contract_trade(
    base: ShadowPaperTrade,
    contract: EconomicContract,
) -> ShadowPaperTrade:
    return base.model_copy(
        update={
            "trade_id": f"{base.trade_id}:{contract.contract_id}",
            "target_r": contract.target_r,
            "target_price": _target_price(base, contract.target_r),
            "max_holding_bars": contract.max_holding_bars,
        }
    )


def _pair_key(trade: ShadowPaperTrade) -> str:
    marker = trade.trade_id.rsplit(":", 1)[0]
    return marker


def _advance_existing(
    state: ShadowPaperState,
    *,
    bars_m5: Sequence[MarketBar],
    trades_path: Path,
) -> None:
    if state.open_trade is None:
        return
    resolved = resolve_open_trade(state.open_trade, bars_m5)
    if resolved.status.value == "open":
        state.open_trade = resolved
        return
    append_closed_trade(trades_path, resolved)
    state.open_trade = None
def _can_open_pair(
    diagnostic: ShadowOpportunityDiagnostic,
    states: Sequence[ShadowPaperState],
    *,
    allow_new_entries: bool,
) -> bool:
    if not allow_new_entries:
        return False
    if any(state.open_trade is not None for state in states):
        return False
    if diagnostic.symbol.upper() != "XAUUSD":
        return False
    if (
        diagnostic.mechanism
        != OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
    ):
        return False
    if diagnostic.state != ShadowSignalState.SIGNAL_EXECUTABLE:
        return False
    if diagnostic.side is None or diagnostic.structural_stop is None:
        return False
    if diagnostic.base_risk is None or not diagnostic.base_risk.approved:
        return False
    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    return all(
        state.last_started_signal_at is None
        or signal_at > state.last_started_signal_at
        for state in states
    )


def advance_xau_structural_displacement_target_pair(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    bars_m5: Sequence[MarketBar],
    runtime_dir: Path,
    evaluated_at: datetime,
    allow_new_entries: bool = True,
) -> PairedEconomicContractReport:
    states = [
        load_shadow_paper_state(_state_path(runtime_dir, contract))
        for contract in XAU_SD_TARGET_CONTRACTS
    ]

    for contract, state in zip(XAU_SD_TARGET_CONTRACTS, states, strict=True):
        _advance_existing(
            state,
            bars_m5=bars_m5,
            trades_path=_trades_path(runtime_dir, contract),
        )
        save_shadow_paper_state(_state_path(runtime_dir, contract), state)

    if _can_open_pair(
        diagnostic,
        states,
        allow_new_entries=allow_new_entries,
    ):
        base = create_paper_trade(
            diagnostic=diagnostic,
            spec=spec,
            evaluated_at=evaluated_at,
        )
        signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
        for contract, state in zip(
            XAU_SD_TARGET_CONTRACTS,
            states,
            strict=True,
        ):
            state.open_trade = _contract_trade(base, contract)
            state.last_started_signal_at = signal_at
            save_shadow_paper_state(_state_path(runtime_dir, contract), state)

    return build_xau_structural_displacement_target_report(runtime_dir)
def _metrics(
    contract: EconomicContract,
    trades: Sequence[ShadowPaperTrade],
) -> EconomicVariantMetrics:
    ordered = sorted(trades, key=lambda trade: (trade.opened_at, trade.trade_id))
    results = [trade.result_r for trade in ordered if trade.result_r is not None]
    gains = sum(value for value in results if value > 0)
    losses = -sum(value for value in results if value < 0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in results:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    total = sum(results)
    return EconomicVariantMetrics(
        contract_id=contract.contract_id,
        role=contract.role,
        closed_trades=len(results),
        total_r=total,
        expectancy_r=total / len(results) if results else 0.0,
        profit_factor=(
            gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)
        ),
        max_drawdown_r=max_drawdown,
    )


def build_xau_structural_displacement_target_report(
    runtime_dir: Path,
) -> PairedEconomicContractReport:
    champion_contract, challenger_contract = XAU_SD_TARGET_CONTRACTS
    champion_trades = load_closed_trades(
        _trades_path(runtime_dir, champion_contract)
    )
    challenger_trades = load_closed_trades(
        _trades_path(runtime_dir, challenger_contract)
    )
    champion_by_pair = {_pair_key(trade): trade for trade in champion_trades}
    challenger_by_pair = {
        _pair_key(trade): trade for trade in challenger_trades
    }
    pair_ids = sorted(set(champion_by_pair) & set(challenger_by_pair))
    paired_champion_trades = [champion_by_pair[pair_id] for pair_id in pair_ids]
    paired_challenger_trades = [
        challenger_by_pair[pair_id] for pair_id in pair_ids
    ]
    comparisons = []
    for pair_id in pair_ids:
        champion_result = champion_by_pair[pair_id].result_r
        challenger_result = challenger_by_pair[pair_id].result_r
        if champion_result is None or challenger_result is None:
            continue
        comparisons.append(
            PairedEconomicComparison(
                pair_id=pair_id,
                champion_result_r=champion_result,
                challenger_result_r=challenger_result,
                delta_r=challenger_result - champion_result,
            )
        )

    open_pair = any(
        load_shadow_paper_state(_state_path(runtime_dir, contract)).open_trade
        is not None
        for contract in XAU_SD_TARGET_CONTRACTS
    )
    return PairedEconomicContractReport(
        family_id="XAUUSD:structural_displacement_sequence",
        comparison_id=PAIR_COMPARISON_ID,
        champion=_metrics(champion_contract, paired_champion_trades),
        challenger=_metrics(
            challenger_contract,
            paired_challenger_trades,
        ),
        paired_trades=len(comparisons),
        delta_total_r=sum(item.delta_r for item in comparisons),
        open_pair=open_pair,
        comparisons=comparisons[-20:],
        broker_authority=False,
        human_review_required=True,
    )

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.domain.broker import BrokerSymbolSpec
from app.domain.family_exit_challenger import (
    ExitChallengerWindowMetrics,
    FamilyExitChallengerReport,
)
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
)
from app.domain.trading import Side
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.opportunity_backtester import _simulate_candidate
from app.services.opportunity_strategies import generate_candidates
from app.services.probe_review import default_probe_review_split
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.runtime_capital import resolve_demo_sizing_capital
from app.services.session_landmarks import build_session_landmark_context

HYPOTHESIS_ID = "xau_sd_target_nearest_frozen_landmark_beyond_1_5r_v1"
CHAMPION_TARGET_R = 1.5
MAX_HOLDING_BARS = 12

@dataclass(frozen=True)
class FrozenLandmarkTarget:
    landmark_type: str | None
    target_price: float | None
    target_r: float


def frozen_landmarks_at_entry(bars: Sequence[MarketBar], candidate: OpportunityCandidate, entry_price: float) -> dict[str, float]:
    context = build_session_landmark_context(bars, candidate.entry_at, entry_price, candidate.side)
    values = {
        "previous_day_high": context.previous_day_high,
        "previous_day_low": context.previous_day_low,
        "asia_high": context.asia_high,
        "asia_low": context.asia_low,
        "london_high_so_far": context.london_high_so_far,
        "london_low_so_far": context.london_low_so_far,
        "us_high_so_far": context.us_high_so_far,
        "us_low_so_far": context.us_low_so_far,
    }
    return {k: v for k, v in values.items() if v is not None}


def select_frozen_landmark_target(bars: Sequence[MarketBar], candidate: OpportunityCandidate, spec: BrokerSymbolSpec, *, slippage_spread_fraction: float) -> FrozenLandmarkTarget:
    entry_bar = bars[candidate.entry_index]
    spread = spec.spread
    slippage = spread * slippage_spread_fraction
    if candidate.side is Side.BUY:
        entry = entry_bar.open + spread + slippage
        stop = candidate.structural_stop
        risk = entry - stop
        champion_price = entry + CHAMPION_TARGET_R * risk
    else:
        entry = entry_bar.open - slippage
        stop = candidate.structural_stop + spread
        risk = stop - entry
        champion_price = entry - CHAMPION_TARGET_R * risk
    levels = frozen_landmarks_at_entry(bars, candidate, entry)
    eligible = [(k, v) for k, v in levels.items() if (candidate.side is Side.BUY and v > champion_price) or (candidate.side is Side.SELL and v < champion_price)]
    if not eligible:
        return FrozenLandmarkTarget(None, None, CHAMPION_TARGET_R)
    name, price = min(eligible, key=lambda x: abs(x[1] - champion_price))
    target_r = (price - entry) / risk if candidate.side is Side.BUY else (entry - price) / risk
    return FrozenLandmarkTarget(name, price, target_r)


def _pf(vals):
    gains=sum(v for v in vals if v>0); losses=-sum(v for v in vals if v<0)
    return gains/losses if losses else (99.0 if gains else 0.0)

def _dd(vals):
    e=p=d=0.0
    for v in vals:
        e+=v; p=max(p,e); d=max(d,p-e)
    return d

def _metrics(rows):
    c=[a.result_r for a,_,_ in rows]; x=[b.result_r for _,b,_ in rows]; n=len(rows)
    cr=Counter(a.exit_reason for a,_,_ in rows); xr=Counter(b.exit_reason for _,b,_ in rows)
    return ExitChallengerWindowMetrics(paired_trades=n, champion_total_r=sum(c), challenger_total_r=sum(x), delta_total_r=sum(x)-sum(c), champion_expectancy_r=sum(c)/n if n else 0, challenger_expectancy_r=sum(x)/n if n else 0, champion_profit_factor=_pf(c), challenger_profit_factor=_pf(x), champion_max_drawdown_r=_dd(c), challenger_max_drawdown_r=_dd(x), champion_targets=cr['target'], challenger_targets=xr['target'], champion_stops=cr['stop'], challenger_stops=xr['stop'], champion_timeouts=cr['timeout'], challenger_timeouts=xr['timeout'], extension_qualified=sum(q for *_,q in rows))

def _pairs(bars, candidates, config):
    out=[]; busy=-1
    for raw in candidates:
        if raw.entry_index<=busy or active_macro_blackouts(config.macro_events, raw.entry_at): continue
        champion_candidate=raw.model_copy(update={'target_r':CHAMPION_TARGET_R,'max_holding_bars':MAX_HOLDING_BARS})
        champion, exit_idx, rej=_simulate_candidate(bars, champion_candidate, config)
        if rej is not None or champion is None or exit_idx is None: continue
        target=select_frozen_landmark_target(bars, champion_candidate, config.spec, slippage_spread_fraction=config.slippage_spread_fraction)
        challenger_candidate=champion_candidate.model_copy(update={'target_r':target.target_r})
        challenger, _, rej2=_simulate_candidate(bars, challenger_candidate, config)
        if rej2 is not None or challenger is None: raise ValueError('landmark challenger simulation failed')
        out.append((champion, challenger, target.landmark_type is not None)); busy=exit_idx
    return out

def build_xau_structural_displacement_landmark_extension(files_dir: Path, *, generated_at: datetime, risk_fraction: float, research_execution_model_path: Path, macro_events_path: Path) -> FamilyExitChallengerReport:
    symbol='XAUUSD'; mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
    capital=resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or capital.capital_eur<=0: raise ValueError('MT4 DEMO sizing capital is unavailable')
    spec=get_mt4_symbol_spec(files_dir,symbol)
    if spec is None: raise ValueError('XAUUSD broker symbol spec is unavailable')
    model=load_research_execution_model(research_execution_model_path)
    if model is not None: spec=apply_research_execution_model(spec,model)
    m5=read_mt4_csv(resolve_mt4_history_path(files_dir,symbol,Timeframe.M5),symbol,Timeframe.M5)
    m15=read_mt4_csv(resolve_mt4_history_path(files_dir,symbol,Timeframe.M15),symbol,Timeframe.M15)
    split=default_probe_review_split()
    config=OpportunityBacktestConfig(spec=spec, mechanism=mechanism, split=split, requested_risk_fraction=risk_fraction, capital_eur=capital.capital_eur, slippage_spread_fraction=0.25, macro_events=load_macro_events(macro_events_path))
    pairs=_pairs(m5, generate_candidates(m5,m15,mechanism), config)
    val=[p for p in pairs if split.train_end<=p[0].signal_at<split.validation_end]; hold=[p for p in pairs if p[0].signal_at>=split.validation_end]
    return FamilyExitChallengerReport(generated_at=generated_at, symbol=symbol, strategy_id=f'{symbol}:{mechanism.value}', hypothesis_id=HYPOTHESIS_ID, change_axis='frozen_landmark_target', champion_target_r=CHAMPION_TARGET_R, challenger_target_r=CHAMPION_TARGET_R, max_holding_bars=MAX_HOLDING_BARS, capital_eur=capital.capital_eur, capital_source=capital.source.value, validation=_metrics(val), holdout=_metrics(hold), authority_effect=False, human_review_required=True, qualification_rule='nearest side-aligned landmark already frozen at entry and strictly beyond 1.5R becomes target; otherwise keep 1.5R', limitations=['Champion cohort frozen by canonical 1.5R overlap policy.','Landmarks are built only from bars fully closed before entry.','No signal, stop, sizing, authority or horizon change.','Research-only.'])

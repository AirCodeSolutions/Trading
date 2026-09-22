import { useEffect, useMemo, useState } from "react";

type RuntimeConfig = {
  execution_mode: string;
  decision_mode: string;
  live_trading_enabled: boolean;
  demo_collection_enabled: boolean;
  demo_execution_bridge_enabled: boolean;
  allowed_timeframes: string[];
  reference_capital_eur: number;
  risk_per_trade_fraction: number;
  absolute_max_risk_fraction: number;
  prospective_min_trades: number;
  historical_validation_min_trades: number;
  historical_holdout_min_trades: number;
};

type ShadowSizing = {
  approved: boolean;
  reason: string;
  lots: number;
  expected_loss_eur: number;
  spread_to_stop: number;
};

type ShadowDiagnostic = {
  symbol: string;
  mechanism: string;
  evaluated_at: string;
  state: "no_signal" | "signal_blocked" | "signal_executable";
  side: "buy" | "sell" | null;
  regime: string;
  regime_direction: number;
  atr_m15: number;
  atr_ratio: number;
  volatility_percentile: number;
  momentum_12_atr: number | null;
  efficiency: number;
  latest_closed_m5_at: string;
  base_risk: ShadowSizing | null;
  reason: string;
};

type PaperTrade = {
  trade_id: string;
  side: "buy" | "sell";
  signal_at: string;
  entry_price: number;
  stop_price: number;
  target_price: number;
  lots: number;
  risk_eur: number;
  status: "open" | "stop" | "target" | "timeout";
  result_r: number | null;
  pnl_eur: number | null;
  bars_held: number;
};

type PaperSummary = {
  closed_trades: number;
  wins: number;
  losses: number;
  total_r: number;
  expectancy_r: number;
  profit_factor: number;
  total_pnl_eur: number;
  legacy_trades: number;
  legacy_total_r: number;
  legacy_pnl_eur: number;
  open_trade: PaperTrade | null;
  recent_trades: PaperTrade[];
};

type MarketUniverseAsset = {
  symbol: string;
  price: number;
  price_source: "broker_quote" | "closed_m5";
  as_of: string;
  bid: number | null;
  ask: number | null;
  spread: number | null;
  quote_live: boolean;
  has_m5: boolean;
  has_m15: boolean;
  broker_spec_ready: boolean;
  research_ready: boolean;
  paper_ready: boolean;
  reason: string;
};

type MarketQualitySnapshot = {
  symbol: string;
  spread_atr_m5: number;
  spread_atr_m15: number;
  min_lot_loss_atr_m15_eur: number;
  required_capital_base_risk_eur: number;
  required_capital_max_risk_eur: number;
  minimum_feasible_risk_fraction: number;
  default_risk_feasible: boolean;
  absolute_risk_feasible: boolean;
  execution_quality_score: number;
  eligible_for_m15_research: boolean;
  reasons: string[];
};

type ProspectiveQualification = {
  strategy_id: string;
  state: "collecting" | "failed" | "supports_demo";
  closed_trades: number;
  expectancy_r: number;
  profit_factor: number;
  max_drawdown_r: number;
  reason: string;
};

type PaperStrategyRuntime = {
  strategy_id: string;
  symbol: string;
  mechanism: string;
  summary: PaperSummary & { max_drawdown_r: number };
  qualification: ProspectiveQualification;
  historical_state: "rejected" | "shadow" | "active" | null;
  historical_weakest_expectancy_r: number | null;
  paper_collection_candidate: boolean;
  paper_entry_allowed: boolean;
};

type TradingOverview = {
  broker: {
    is_demo: boolean;
    balance: number;
    equity: number;
    margin: number;
    free_margin: number;
    observed_positions: number;
  } | null;
  risk: {
    reference_capital_eur: number;
    research_paper_closed_pnl_eur: number;
    research_paper_total_r: number;
    research_paper_legacy_closed_pnl_eur: number;
    research_paper_legacy_total_r: number;
    research_paper_legacy_trades: number;
    research_paper_open_risk_eur: number;
    research_paper_open_positions: number;
    selected_daily_pnl_eur: number;
    selected_daily_r: number;
    selected_open_risk_eur: number;
    selected_open_positions: number;
    max_daily_loss_eur: number;
    remaining_daily_loss_budget_eur: number;
  };
  portfolio: {
    action: "no_trade" | "paper_only" | "demo_collection" | "demo_eligible";
    selected_strategy_id: string | null;
    reason: string;
    historical_active: boolean;
    prospective_supports_demo: boolean;
  };
  qualifications: ProspectiveQualification[];
  paper_strategies: PaperStrategyRuntime[];
};

type CostSummary = Record<
  string,
  {
    samples: number;
    average_spread: number;
    max_spread: number;
    average_spread_pct: number;
  }
>;

type MacroEvent = {
  event_id: string;
  name: string;
  start_at: string;
  end_at: string;
  impact: "medium" | "high";
  currencies: string[];
  source: string;
};

type MacroStatus = {
  at: string;
  blocked: boolean;
  active_events: MacroEvent[];
  next_event: MacroEvent | null;
  reason: string;
};

type DemoExecutionStatus = {
  guard: {
    at: string;
    ready: boolean;
    execution_mode: string;
    bridge_enabled: boolean;
    live_trading_enabled: boolean;
    broker_is_demo: boolean;
    portfolio_action: "no_trade" | "paper_only" | "demo_collection" | "demo_eligible";
    macro_blocked: boolean;
    broker_observed_positions: number;
    bridge_open_positions: number;
    reasons: string[];
  };
  collection_state: {
    paper_trade_id: string | null;
    strategy_id: string | null;
    open_command_id: string | null;
    ticket: number | null;
    close_command_id: string | null;
    last_completed_trade_id: string | null;
    last_error: string | null;
  } | null;
  pending_command: {
    command_id: string;
    symbol: string;
    side: "buy" | "sell";
    lots: number;
    strategy_id: string;
  } | null;
  pending_close_command: {
    command_id: string;
    ticket: number;
    strategy_id: string;
  } | null;
  latest_result: {
    command_id: string;
    status: string;
    ticket: number;
    error_code: number;
    fill_price: number;
    processed_at: string;
  } | null;
  bridge_positions: {
    ticket: number;
    symbol: string;
    side: "buy" | "sell";
    lots: number;
    open_price: number;
    stop_loss: number;
    take_profit: number;
    profit: number;
    open_time: string;
    strategy_comment: string;
  }[];
};

type ManualDemoPreview = {
  at: string;
  symbol: string;
  side: "buy" | "sell";
  bid: number;
  ask: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_fraction: number;
  reward_distance: number;
  reward_risk_ratio: number;
  quote_age_seconds: number;
  remaining_daily_loss_budget_eur: number;
  approved: boolean;
  reasons: string[];
  sizing: {
    approved: boolean;
    reason: string;
    risk_fraction: number;
    risk_budget_eur: number;
    stop_distance: number;
    spread: number;
    spread_to_stop: number;
    raw_lots: number;
    lots: number;
    expected_loss_eur: number;
    min_lot_loss_eur: number;
    estimated_margin_eur: number;
  } | null;
};

type SessionPreflight = {
  at: string;
  status: "ready" | "warming_up" | "waiting_market" | "degraded" | "blocked";
  worker_ok: boolean;
  worker_age_seconds: number | null;
  macro_blocked: boolean;
  portfolio_action: string;
  demo_execution_ready: boolean;
  ready_symbols: string[];
  warming_symbols: string[];
  waiting_symbols: string[];
  degraded_symbols: string[];
  assets: {
    symbol: string;
    state: "ready" | "warming_up" | "waiting_quote" | "m5_stalled" | "missing_spec" | "missing_history";
    quote_live: boolean;
    paper_ready: boolean;
    broker_spec_ready: boolean;
    has_m5: boolean;
    has_m15: boolean;
    reason: string;
  }[];
  timeline: {
    symbol: string;
    quote_live_since: string | null;
    first_fresh_m5_at: string | null;
    ready_at: string | null;
    m5_stalled_at: string | null;
    last_closed_m5_at: string | null;
  }[];
  reason: string;
};

type BlockedProbe = {
  probe_id: string;
  symbol: string;
  mechanism: string;
  side: "buy" | "sell";
  signal_at: string;
  entry_price: number;
  stop_price: number;
  target_price: number;
  block_reason: string;
  max_risk_approved: boolean;
  max_risk_reason: string | null;
  min_lot_loss_eur: number;
  required_capital_base_risk_eur: number;
  required_capital_max_risk_eur: number;
  minimum_feasible_risk_fraction: number;
  capital_granularity_feasible_under_max_risk: boolean;
  status: "open" | "stop" | "target" | "timeout";
  result_r: number | null;
};

type BlockedProbeRuntime = {
  strategy_id: string;
  symbol: string;
  mechanism: string;
  summary: {
    closed_probes: number;
    wins: number;
    losses: number;
    total_r: number;
    expectancy_r: number;
    profit_factor: number;
    open_probe: BlockedProbe | null;
    recent_probes: BlockedProbe[];
  };
};

type OpportunityFunnelStrategy = {
  strategy_id: string;
  symbol: string;
  mechanism: string;
  signal_rows: number;
  blocked_signal_rows: number;
  executable_signal_rows: number;
  tracked_blocked_probes: number;
  resolved_blocked_probes: number;
  open_blocked_probes: number;
  blocked_wins: number;
  blocked_losses: number;
  blocked_total_r: number;
  blocked_expectancy_r: number;
  blocked_feasible_under_max_risk: number;
  capital_limited_probes: number;
  capital_base_feasible_probes: number;
  capital_max_feasible_probes: number;
  capital_base_feasible_resolved_probes: number;
  capital_base_feasible_wins: number;
  capital_base_feasible_losses: number;
  capital_base_feasible_total_r: number;
  capital_base_feasible_expectancy_r: number;
  min_required_capital_base_risk_eur: number | null;
  max_required_capital_base_risk_eur: number | null;
  block_reasons: Record<string, number>;
};

type OpportunityFunnel = {
  window_hours: number;
  window_start: string;
  window_end: string;
  reference_capital_eur: number;
  base_risk_budget_eur: number;
  absolute_max_risk_budget_eur: number;
  signal_rows: number;
  blocked_signal_rows: number;
  executable_signal_rows: number;
  tracked_blocked_probes: number;
  resolved_blocked_probes: number;
  open_blocked_probes: number;
  blocked_wins: number;
  blocked_losses: number;
  blocked_total_r: number;
  blocked_expectancy_r: number;
  blocked_feasible_under_max_risk: number;
  capital_limited_probes: number;
  capital_base_feasible_probes: number;
  capital_max_feasible_probes: number;
  capital_base_feasible_resolved_probes: number;
  capital_base_feasible_wins: number;
  capital_base_feasible_losses: number;
  capital_base_feasible_total_r: number;
  capital_base_feasible_expectancy_r: number;
  block_reasons: Record<string, number>;
  strategies: OpportunityFunnelStrategy[];
};



type TradeIntelligence = {
  trade_id: string;
  source: "paper" | "blocked_probe";
  symbol: string;
  mechanism: string;
  side: "buy" | "sell";
  signal_at: string;
  opened_at: string;
  exit_at: string | null;
  status: string;
  result_r: number | null;
  pnl_eur: number | null;
  mfe_r: number;
  mae_r: number;
  r_lost_while_waiting: number;
  rr_at_signal: number | null;
  rr_at_entry: number | null;
  mfe_consumed_before_entry_r: number;
  block_reason: string | null;
};

type TradingIntelligence = {
  generated_at: string;
  window_hours: number;
  market_move_threshold_atr: number;
  market_move_horizon_bars: number;
  trades: TradeIntelligence[];
  opportunities: {
    episode_id: string;
    symbol: string;
    side: "buy" | "sell";
    birth_at: string;
    horizon_end_at: string;
    reference_price: number;
    atr_m5: number;
    move_atr: number;
    capture_state: "executable" | "blocked" | "missed";
    matching_strategies: string[];
    causal_context: {
      pattern:
        | "auction_failure_reclaim"
        | "compression_breakout"
        | "directional_displacement"
        | "structural_extreme_stretch"
        | "compression_state"
        | "structural_extreme"
        | "unclassified";
      side: "buy" | "sell" | null;
      aligned_with_move: boolean | null;
      range_position_24: number;
      return_3_atr: number;
      return_6_atr: number;
      compression_6_24: number;
      body_fraction: number;
      sweep_atr: number;
      reclaim_atr: number;
      evidence: string[];
    };
  }[];
  assets: {
    symbol: string;
    paper_closed_trades: number;
    paper_total_r: number;
    blocked_closed_probes: number;
    blocked_total_r: number;
    market_opportunities: number;
    captured_executable: number;
    captured_blocked: number;
    missed_opportunities: number;
    capture_rate: number;
    average_r_lost_while_waiting: number;
    average_mfe_r: number;
    average_mae_r: number;
  }[];
  causal_patterns: {
    pattern:
      | "auction_failure_reclaim"
      | "compression_breakout"
      | "directional_displacement"
      | "structural_extreme_stretch"
      | "compression_state"
      | "structural_extreme"
      | "unclassified";
    episodes: number;
    missed: number;
    aligned: number;
    opposed: number;
    no_direction: number;
    average_move_atr: number;
  }[];
  limitations: string[];
};

type EconomicFeasibilityReport = {
  generated_at: string;
  reference_capital_eur: number;
  risk_fraction: number;
  max_spread_to_stop: number;
  max_margin_fraction: number;
  stop_atr_multiples: number[];
  assets: {
    symbol: string;
    frozen_spread: number;
    min_lot: number;
    min_lot_margin_eur: number;
    spread_stop_floor_price: number;
    risk_stop_ceiling_price: number;
    feasible_stop_interval: boolean;
    minimum_reference_capital_eur: number;
    total_episodes: number;
    stop_profiles: {
      stop_atr_multiple: number;
      episodes: number;
      approved: number;
      rejected_spread: number;
      rejected_min_lot: number;
      rejected_margin: number;
      rejected_other: number;
      approval_rate: number;
      average_expected_loss_eur: number;
      average_lots: number;
    }[];
  }[];
};

type DashboardView = "overview" | "trading" | "markets" | "research";

type DailyTradingReport = {
  report_date: string;
  generated_at: string;
  reference_capital_eur: number;
  execution_mode: string;
  live_trading_enabled: boolean;
  broker_is_demo: boolean;
  portfolio_action: string;
  portfolio_reason: string;
  paper_closed_pnl_eur_today: number;
  paper_closed_r_today: number;
  paper_open_positions: number;
  paper_open_risk_eur: number;
  bridge_open_positions: number;
  bridge_unrealized_pnl_eur: number;
  broker_realized_pnl_eur_today: number | null;
  market_opportunities_24h: number;
  captured_opportunities_24h: number;
  missed_opportunities_24h: number;
  qualification_counts: Record<string, number>;
  execution_quality: {
    commands: number;
    fills: number;
    refused: number;
    errors: number;
    unpaired_results: number;
    average_adverse_slippage_price: number;
    max_adverse_slippage_price: number;
    average_slippage_r: number;
  };
  assets: {
    symbol: string;
    state: "collect_prospective" | "degraded" | "research_only";
    paper_eligible_strategies: string[];
    qualification_states: Record<string, string>;
    market_opportunities_24h: number;
    captured_opportunities_24h: number;
    missed_opportunities_24h: number;
    capture_rate_24h: number;
    blocked_expectancy_r_24h: number;
    next_action: string;
  }[];
  limitations: string[];
};

type QualificationHistoryEvent = {
  at: string;
  strategy_id: string;
  state: "collecting" | "failed" | "supports_demo";
  closed_trades: number;
  expectancy_r: number;
  profit_factor: number;
  max_drawdown_r: number;
  reason: string;
};

type MarketQuote = {
  symbol: string;
  as_of: string;
  bid: number;
  ask: number;
  mid: number;
  spread: number;
  spread_pct: number;
  digits: number;
  age_seconds: number;
  status: "live" | "stale";
  last_closed_m5_at: string | null;
  recent_change_pct: number | null;
  recent_m5_closes: number[];
};

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? "—" : value.toFixed(digits);
}

function formatPrice(value: number, digits: number) {
  return value.toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

function formatAge(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

function stateLabel(state: ShadowDiagnostic["state"] | undefined) {
  if (state === "signal_executable") return "SIGNAL EXÉCUTABLE";
  if (state === "signal_blocked") return "SIGNAL BLOQUÉ";
  if (state === "no_signal") return "NO SIGNAL";
  return "—";
}

function Sparkline({ values }: { values: number[] }) {
  const points = useMemo(() => {
    if (values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return values
      .map((value, index) => {
        const x = (index / (values.length - 1)) * 100;
        const y = 34 - ((value - min) / range) * 30;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  }, [values]);

  return (
    <svg className="sparkline" viewBox="0 0 100 38" role="img" aria-label="Évolution récente M5">
      <polyline points={points} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function MarketCard({ quote }: { quote: MarketQuote }) {
  const changeClass =
    quote.recent_change_pct == null
      ? ""
      : quote.recent_change_pct >= 0
        ? "positive"
        : "negative";

  return (
    <article className="market-card">
      <div className="market-card-top">
        <div>
          <span className="market-symbol">{quote.symbol}</span>
          <span className={`feed-status feed-${quote.status}`}>
            {quote.status === "live" ? "LIVE" : "STALE"}
          </span>
        </div>
        <span className="quote-age">{formatAge(quote.age_seconds)}</span>
      </div>

      <div className="market-price">
        {formatPrice(quote.mid, quote.digits)}
      </div>

      <div className="quote-row">
        <span>
          BID <strong>{formatPrice(quote.bid, quote.digits)}</strong>
        </span>
        <span>
          ASK <strong>{formatPrice(quote.ask, quote.digits)}</strong>
        </span>
      </div>

      <Sparkline values={quote.recent_m5_closes} />

      <div className="market-footer">
        <span>
          Spread <strong>{formatPrice(quote.spread, quote.digits)}</strong>
        </span>
        <span className={changeClass}>
          M5 récent{" "}
          <strong>
            {quote.recent_change_pct == null
              ? "—"
              : `${quote.recent_change_pct >= 0 ? "+" : ""}${quote.recent_change_pct.toFixed(2)} %`}
          </strong>
        </span>
      </div>

      <div className="quote-time">
        Dernière cote : {new Date(quote.as_of).toLocaleString("fr-FR")}
      </div>
    </article>
  );
}

export default function App() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [shadow, setShadow] = useState<ShadowDiagnostic | null>(null);
  const [opportunities, setOpportunities] = useState<ShadowDiagnostic[]>([]);
  const [blockedProbes, setBlockedProbes] = useState<BlockedProbeRuntime[]>([]);
  const [opportunityFunnel, setOpportunityFunnel] = useState<OpportunityFunnel | null>(null);
  const [intelligence, setIntelligence] = useState<TradingIntelligence | null>(null);
  const [economicFeasibility, setEconomicFeasibility] = useState<EconomicFeasibilityReport | null>(null);
  const [dailyReport, setDailyReport] = useState<DailyTradingReport | null>(null);
  const [qualificationHistory, setQualificationHistory] = useState<QualificationHistoryEvent[]>([]);
  const [paper, setPaper] = useState<PaperSummary | null>(null);
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [universe, setUniverse] = useState<MarketUniverseAsset[]>([]);
  const [marketQuality, setMarketQuality] = useState<MarketQualitySnapshot[]>([]);
  const [overview, setOverview] = useState<TradingOverview | null>(null);
  const [costs, setCosts] = useState<CostSummary>({});
  const [macro, setMacro] = useState<MacroStatus | null>(null);
  const [demo, setDemo] = useState<DemoExecutionStatus | null>(null);
  const [preflight, setPreflight] = useState<SessionPreflight | null>(null);
  const [status, setStatus] = useState("Connexion au backend…");
  const [activeView, setActiveView] = useState<DashboardView>("overview");
  const [manualSymbol, setManualSymbol] = useState("BTCUSD");
  const [manualSide, setManualSide] = useState<"buy" | "sell">("buy");
  const [manualStop, setManualStop] = useState("");
  const [manualTarget, setManualTarget] = useState("");
  const [manualRiskPct, setManualRiskPct] = useState("1");
  const [manualPreview, setManualPreview] = useState<ManualDemoPreview | null>(null);
  const [manualBusy, setManualBusy] = useState(false);
  const [manualMessage, setManualMessage] = useState("");

  useEffect(() => {
    let active = true;
    let refreshing = false;

    const refreshCore = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const [
          healthResponse,
          configResponse,
          shadowResponse,
          paperResponse,
          universeResponse,
          qualityResponse,
          overviewResponse,
          costsResponse,
          macroResponse,
          demoResponse,
          preflightResponse,
          opportunitiesResponse,
          blockedProbesResponse,
          opportunityFunnelResponse,
          intelligenceResponse,
          economicFeasibilityResponse,
          dailyReportResponse,
          qualificationHistoryResponse
        ] = await Promise.all([
          fetch("/api/v1/health"),
          fetch("/api/v1/config"),
          fetch("/api/v1/shadow/mt4/btc/break-retest"),
          fetch("/api/v1/shadow/mt4/btc/break-retest/paper"),
          fetch("/api/v1/market/mt4/universe"),
          fetch("/api/v1/market/mt4/quality"),
          fetch("/api/v1/portfolio/overview"),
          fetch("/api/v1/market/mt4/costs"),
          fetch("/api/v1/macro/status"),
          fetch("/api/v1/execution/demo/status"),
          fetch("/api/v1/session/preflight"),
          fetch("/api/v1/shadow/overview"),
          fetch("/api/v1/shadow/blocked-probes"),
          fetch("/api/v1/shadow/opportunity-funnel?hours=24"),
          fetch("/api/v1/intelligence/overview?hours=24"),
          fetch("/api/v1/research/economic-feasibility"),
          fetch("/api/v1/reports/daily"),
          fetch("/api/v1/qualification/history?limit=50")
        ]);
        if (!healthResponse.ok || !configResponse.ok) {
          throw new Error("backend unavailable");
        }

        const health = await healthResponse.json();
        const runtime = await configResponse.json();
        const shadowPayload = shadowResponse.ok ? await shadowResponse.json() : null;
        const paperPayload = paperResponse.ok ? await paperResponse.json() : null;
        const universePayload = universeResponse.ok ? await universeResponse.json() : [];
        const qualityPayload = qualityResponse.ok ? await qualityResponse.json() : [];
        const overviewPayload = overviewResponse.ok ? await overviewResponse.json() : null;
        const costsPayload = costsResponse.ok ? await costsResponse.json() : {};
        const macroPayload = macroResponse.ok ? await macroResponse.json() : null;
        const demoPayload = demoResponse.ok ? await demoResponse.json() : null;
        const preflightPayload = preflightResponse.ok
          ? await preflightResponse.json()
          : null;
        const opportunitiesPayload = opportunitiesResponse.ok
          ? await opportunitiesResponse.json()
          : [];
        const blockedProbesPayload = blockedProbesResponse.ok
          ? await blockedProbesResponse.json()
          : [];
        const opportunityFunnelPayload = opportunityFunnelResponse.ok
          ? await opportunityFunnelResponse.json()
          : null;
        const intelligencePayload = intelligenceResponse.ok
          ? await intelligenceResponse.json()
          : null;
        const economicFeasibilityPayload = economicFeasibilityResponse.ok
          ? await economicFeasibilityResponse.json()
          : null;
        const dailyReportPayload = dailyReportResponse.ok
          ? await dailyReportResponse.json()
          : null;
        const qualificationHistoryPayload = qualificationHistoryResponse.ok
          ? await qualificationHistoryResponse.json()
          : [];

        if (!active) return;
        setStatus(health.status === "ok" ? "Opérationnel" : "Dégradé");
        setConfig(runtime);
        setShadow(shadowPayload);
        setPaper(paperPayload);
        setUniverse(universePayload);
        setMarketQuality(qualityPayload);
        setOverview(overviewPayload);
        setCosts(costsPayload);
        setMacro(macroPayload);
        setDemo(demoPayload);
        setPreflight(preflightPayload);
        setOpportunities(opportunitiesPayload);
        setBlockedProbes(blockedProbesPayload);
        setOpportunityFunnel(opportunityFunnelPayload);
        setIntelligence(intelligencePayload);
        setEconomicFeasibility(economicFeasibilityPayload);
        setDailyReport(dailyReportPayload);
        setQualificationHistory(qualificationHistoryPayload);
      } catch {
        if (active) setStatus("Backend indisponible");
      } finally {
        refreshing = false;
      }
    };

    void refreshCore();
    const timer = window.setInterval(refreshCore, 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let active = true;
    let refreshing = false;

    const refreshQuotes = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const response = await fetch("/api/v1/market/mt4/live");
        if (!response.ok) throw new Error("market feed unavailable");
        const payload = (await response.json()) as MarketQuote[];
        if (active) setQuotes(payload);
      } catch {
        if (active) setQuotes([]);
      } finally {
        refreshing = false;
      }
    };

    void refreshQuotes();
    const timer = window.setInterval(refreshQuotes, 5_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const liveCount = quotes.filter((quote) => quote.status === "live").length;
  const paperCandidates = overview?.paper_strategies.filter(
    (row) => row.paper_entry_allowed
  ) ?? [];
  const bestProspective = paperCandidates.reduce<PaperStrategyRuntime | null>(
    (best, row) =>
      best == null || row.summary.closed_trades > best.summary.closed_trades ? row : best,
    null
  );
  const prospectiveTarget = config?.prospective_min_trades ?? 20;
  const prospectiveProgress = bestProspective?.summary.closed_trades ?? 0;
  const demoTransportArmed =
    config?.execution_mode === "demo" &&
    config.demo_collection_enabled &&
    config.demo_execution_bridge_enabled;
  const demoBridgeLabel = demo?.guard.ready
    ? "READY"
    : demoTransportArmed
      ? "ARMED"
      : "DISARMED";
  const demoRoadmapTitle = demo?.guard.ready
    ? "DEMO ORDER READY"
    : demoTransportArmed
      ? "DEMO COLLECTION ARMÉE"
      : "PAPER / RESEARCH ONLY";
  const automaticTradingLabel = config?.live_trading_enabled
    ? "LIVE ACTIF"
    : demoTransportArmed
      ? "DEMO AUTO ARMÉ"
      : "OFF · PAPER ONLY";
  const openPaperRows =
    overview?.paper_strategies.filter((row) => row.summary.open_trade != null) ?? [];
  const eligibleOpenPaperRows = openPaperRows.filter((row) => row.paper_entry_allowed);
  const demoCollectionCandidates =
    overview?.paper_strategies.filter(
      (row) =>
        row.historical_state === "shadow" &&
        row.paper_entry_allowed
    ) ?? [];
  const openDemoCollectionCandidates = openPaperRows.filter(
    (row) =>
      row.historical_state === "shadow" &&
      row.paper_entry_allowed
  );
  const retainedSymbols = ["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"];
  const strategyByAsset = retainedSymbols.map((symbol) => {
    const rows = overview?.paper_strategies.filter((row) => row.symbol === symbol) ?? [];
    const eligible = rows.filter((row) => row.paper_entry_allowed);
    return { symbol, rows, eligible };
  });
  const selectedManualQuote = quotes.find((quote) => quote.symbol === manualSymbol) ?? null;
  const recentPaperTrades = (overview?.paper_strategies ?? [])
    .flatMap((row) =>
      row.summary.recent_trades.map((trade) => ({
        strategy_id: row.strategy_id,
        symbol: row.symbol,
        trade
      }))
    )
    .sort(
      (left, right) =>
        new Date(right.trade.signal_at).getTime() - new Date(left.trade.signal_at).getTime()
    )
    .slice(0, 10);
  const topMissedOpportunities = (intelligence?.opportunities ?? [])
    .filter((episode) => episode.capture_state === "missed")
    .sort((left, right) => right.move_atr - left.move_atr)
    .slice(0, 12);
  const executableOpportunities = opportunities.filter(
    (item) => item.state === "signal_executable"
  ).length;
  const tradingNewPositions = demo?.bridge_positions.length ?? 0;
  const paperPnlToday = dailyReport?.paper_closed_pnl_eur_today ?? 0;
  const systemReady = preflight?.status === "ready";
  const autoDemoState = tradingNewPositions
    ? "POSITION OUVERTE"
    : demoTransportArmed
      ? "ARMÉ · EN ATTENTE"
      : "DÉSARMÉ";

  const refreshExecutionState = async () => {
    const [overviewResponse, demoResponse, preflightResponse] = await Promise.all([
      fetch("/api/v1/portfolio/overview"),
      fetch("/api/v1/execution/demo/status"),
      fetch("/api/v1/session/preflight")
    ]);
    if (overviewResponse.ok) setOverview(await overviewResponse.json());
    if (demoResponse.ok) setDemo(await demoResponse.json());
    if (preflightResponse.ok) setPreflight(await preflightResponse.json());
  };

  const manualPayload = () => ({
    symbol: manualSymbol,
    side: manualSide,
    stop_loss: Number(manualStop),
    take_profit: Number(manualTarget),
    risk_fraction: Number(manualRiskPct) / 100
  });

  const previewManualTrade = async () => {
    const payload = manualPayload();
    if (
      !Number.isFinite(payload.stop_loss) ||
      !Number.isFinite(payload.take_profit) ||
      !Number.isFinite(payload.risk_fraction) ||
      payload.stop_loss <= 0 ||
      payload.take_profit <= 0 ||
      payload.risk_fraction <= 0
    ) {
      setManualPreview(null);
      setManualMessage("Renseigne un SL, un TP et un risque valides.");
      return;
    }

    setManualBusy(true);
    setManualMessage("");
    try {
      const response = await fetch("/api/v1/execution/demo/manual/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const preview = (await response.json()) as ManualDemoPreview;
      if (!response.ok) throw new Error("Prévisualisation impossible.");
      setManualPreview(preview);
      setManualMessage(
        preview.approved
          ? "Preview validée. Vérifie les chiffres avant de confirmer."
          : preview.reasons.join(" · ")
      );
    } catch (error) {
      setManualPreview(null);
      setManualMessage(error instanceof Error ? error.message : "Prévisualisation impossible.");
    } finally {
      setManualBusy(false);
    }
  };

  const submitManualTrade = async () => {
    if (!manualPreview?.approved) return;
    const confirmation = window.confirm(
      "Confirmer l’ordre DEMO " +
        manualSide.toUpperCase() +
        " " +
        manualSymbol +
        " ?\nSL " +
        manualStop +
        " · TP " +
        manualTarget +
        " · risque " +
        manualRiskPct +
        "%"
    );
    if (!confirmation) return;

    setManualBusy(true);
    setManualMessage("");
    try {
      const response = await fetch("/api/v1/execution/demo/manual/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...manualPayload(), confirmed: true })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Ordre DEMO refusé.");
      }
      setManualPreview(null);
      setManualMessage(
        "Commande DEMO envoyée : " +
          String(payload.side).toUpperCase() +
          " " +
          payload.symbol +
          " " +
          Number(payload.lots).toFixed(2) +
          " lot."
      );
      await refreshExecutionState();
    } catch (error) {
      setManualMessage(error instanceof Error ? error.message : "Ordre DEMO refusé.");
    } finally {
      setManualBusy(false);
    }
  };

  const closeManualTrade = async (ticket: number) => {
    if (!window.confirm("Fermer la position manuelle DEMO #" + ticket + " ?")) return;
    setManualBusy(true);
    setManualMessage("");
    try {
      const response = await fetch("/api/v1/execution/demo/manual/close/" + ticket, {
        method: "POST"
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Fermeture DEMO refusée.");
      }
      setManualMessage("Commande de fermeture envoyée pour le ticket #" + ticket + ".");
      await refreshExecutionState();
    } catch (error) {
      setManualMessage(error instanceof Error ? error.message : "Fermeture DEMO refusée.");
    } finally {
      setManualBusy(false);
    }
  };

  return (
    <main className="shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">TRADING-NEW · MT4 · M5 / M15</p>
          <h1>Trading Control Center</h1>
          <p className="subtitle">
            Pilotage quotidien en premier. Les détails marchés et recherche restent accessibles
            sans encombrer la vue principale.
          </p>
        </div>
        <div className={systemReady ? "system-pill system-pill-ready" : "system-pill system-pill-warning"}>
          <span className="system-dot" />
          <div>
            <small>SYSTÈME</small>
            <strong>{systemReady ? "READY" : status.toUpperCase()}</strong>
          </div>
        </div>
      </header>

      <section className="command-center">
        <div className="command-center-heading">
          <div>
            <span className="label">SITUATION EN UN COUP D’ŒIL</span>
            <strong>{automaticTradingLabel}</strong>
          </div>
          <span className={demoTransportArmed ? "command-status command-status-ready" : "command-status"}>
            {overview?.broker?.is_demo ? "BROKER DEMO" : "BROKER —"}
          </span>
        </div>
        <div className="command-center-grid">
          <article>
            <span>Système</span>
            <strong className={systemReady ? "positive-text" : "negative-text"}>
              {systemReady ? "5/5 READY" : preflight?.status.replaceAll("_", " ").toUpperCase() ?? "—"}
            </strong>
            <small>Worker {preflight?.worker_ok ? "OK" : "KO"}</small>
          </article>
          <article>
            <span>Auto DEMO</span>
            <strong className={demoTransportArmed ? "positive-text" : ""}>{autoDemoState}</strong>
            <small>LIVE {config?.live_trading_enabled ? "ON" : "OFF"}</small>
          </article>
          <article>
            <span>Positions Trading-New</span>
            <strong>{tradingNewPositions}</strong>
            <small>{demo?.pending_command || demo?.pending_close_command ? "commande en attente" : "aucune commande"}</small>
          </article>
          <article>
            <span>PnL PAPER aujourd’hui</span>
            <strong className={paperPnlToday >= 0 ? "positive-text" : "negative-text"}>
              {dailyReport ? `${paperPnlToday >= 0 ? "+" : ""}${paperPnlToday.toFixed(2)} €` : "—"}
            </strong>
            <small>{dailyReport ? `${dailyReport.paper_closed_r_today >= 0 ? "+" : ""}${dailyReport.paper_closed_r_today.toFixed(2)} R` : "—"}</small>
          </article>
          <article>
            <span>Opportunités exécutables</span>
            <strong>{executableOpportunities}</strong>
            <small>{opportunities.length} scanners</small>
          </article>
          <article>
            <span>Macro</span>
            <strong className={macro?.blocked ? "negative-text" : "positive-text"}>
              {macro ? (macro.blocked ? "BLOCKED" : "CLEAR") : "—"}
            </strong>
            <small>{macro?.next_event?.name ?? "aucun événement chargé"}</small>
          </article>
          <article>
            <span>Preuve prospective</span>
            <strong>{prospectiveProgress}/{prospectiveTarget}</strong>
            <small>{paperCandidates.length} stratégie(s) PAPER-éligible(s)</small>
          </article>
        </div>
      </section>

      <nav className="dashboard-nav" aria-label="Navigation du dashboard">
        {([
          ["overview", "Vue d’ensemble", "Pilotage"],
          ["trading", "Trading", "Exécution"],
          ["markets", "Marchés", "Prix & coûts"],
          ["research", "Recherche", "Evidence"]
        ] as [DashboardView, string, string][]).map(([view, label, hint]) => (
          <button
            key={view}
            type="button"
            className={activeView === view ? "dashboard-nav-button active" : "dashboard-nav-button"}
            aria-pressed={activeView === view}
            onClick={() => setActiveView(view)}
          >
            <strong>{label}</strong>
            <span>{hint}</span>
          </button>
        ))}
      </nav>

      <section
        hidden={activeView !== "overview"}
        className={`preflight-panel preflight-${preflight?.status ?? "unknown"}`}
      >
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">SESSION PREFLIGHT · REPRISE AUTOMATIQUE</p>
            <h2>{preflight?.status.replaceAll("_", " ").toUpperCase() ?? "CHARGEMENT"}</h2>
          </div>
          <span className="badge">
            Worker {preflight?.worker_ok ? "OK" : "KO"}
            {preflight?.worker_age_seconds != null
              ? ` · ${Math.round(preflight.worker_age_seconds)} s`
              : ""}
          </span>
        </div>

        <div className="preflight-metrics">
          <div>
            <span>READY</span>
            <strong>{preflight?.ready_symbols.join(", ") || "—"}</strong>
          </div>
          <div>
            <span>WARMING UP</span>
            <strong>{preflight?.warming_symbols.join(", ") || "—"}</strong>
          </div>
          <div>
            <span>EN ATTENTE MARCHÉ</span>
            <strong>{preflight?.waiting_symbols.join(", ") || "—"}</strong>
          </div>
          <div>
            <span>DÉGRADÉ</span>
            <strong>{preflight?.degraded_symbols.join(", ") || "—"}</strong>
          </div>
          <div>
            <span>MACRO</span>
            <strong>{preflight ? (preflight.macro_blocked ? "BLOCKED" : "CLEAR") : "—"}</strong>
          </div>
          <div>
            <span>PORTFOLIO</span>
            <strong>{preflight?.portfolio_action.replaceAll("_", " ").toUpperCase() ?? "—"}</strong>
          </div>
          <div>
            <span>DEMO</span>
            <strong>{preflight ? (preflight.demo_execution_ready ? "READY" : "LOCKED") : "—"}</strong>
          </div>
        </div>

        <p className="preflight-reason">
          {preflight?.reason ?? "Vérification de la session en cours…"}
        </p>

        {preflight?.timeline.length ? (
          <details className="preflight-details">
            <summary>Détails techniques par actif</summary>
            <div className="session-timeline">
              <div className="timeline-row timeline-head">
                <span>Actif</span>
                <span>Quote LIVE</span>
                <span>1re M5 fraîche</span>
                <span>Dernière M5</span>
                <span>READY</span>
                <span>Stall</span>
              </div>
              {preflight.timeline.map((item) => (
                <div className="timeline-row" key={item.symbol}>
                  <strong>{item.symbol}</strong>
                  <span>{item.quote_live_since ? new Date(item.quote_live_since).toLocaleTimeString("fr-FR") : "—"}</span>
                  <span>{item.first_fresh_m5_at ? new Date(item.first_fresh_m5_at).toLocaleTimeString("fr-FR") : "—"}</span>
                  <span>{item.last_closed_m5_at ? new Date(item.last_closed_m5_at).toLocaleTimeString("fr-FR") : "—"}</span>
                  <span>{item.ready_at ? new Date(item.ready_at).toLocaleTimeString("fr-FR") : "—"}</span>
                  <span className={item.m5_stalled_at ? "negative-text" : ""}>
                    {item.m5_stalled_at ? new Date(item.m5_stalled_at).toLocaleTimeString("fr-FR") : "—"}
                  </span>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </section>

      <section className="grid legacy-summary-grid" hidden>
        <article className="card">
          <span className="label">Système</span>
          <strong>{status}</strong>
        </article>
        <article className="card">
          <span className="label">Flux marché</span>
          <strong>{quotes.length ? `${liveCount}/${quotes.length} LIVE` : "—"}</strong>
        </article>
        <article className="card">
          <span className="label">Portfolio Manager</span>
          <strong>{overview?.portfolio.action.replaceAll("_", " ") ?? "—"}</strong>
        </article>
        <article className="card">
          <span className="label">Capital référence</span>
          <strong>{config ? `${config.reference_capital_eur.toFixed(0)} €` : "—"}</strong>
        </article>
        <article className="card">
          <span className="label">PnL evidence post-cutover</span>
          <strong>
            {overview
              ? `${overview.risk.research_paper_closed_pnl_eur >= 0 ? "+" : ""}${overview.risk.research_paper_closed_pnl_eur.toFixed(2)} €`
              : "—"}
          </strong>
        </article>
        <article className="card">
          <span className="label">Legacy pré-cutover</span>
          <strong>
            {overview
              ? `${overview.risk.research_paper_legacy_trades} trades · ${overview.risk.research_paper_legacy_total_r.toFixed(2)} R`
              : "—"}
          </strong>
        </article>
        <article className="card">
          <span className="label">Live trading</span>
          <strong>{config?.live_trading_enabled ? "ACTIF" : "VERROUILLÉ"}</strong>
        </article>
        <article className="card">
          <span className="label">Macro Gate</span>
          <strong className={macro?.blocked ? "negative-text" : "positive-text"}>
            {macro ? (macro.blocked ? "BLOCKED" : "CLEAR") : "—"}
          </strong>
        </article>
        <article className="card">
          <span className="label">Bridge DEMO</span>
          <strong className={demo?.guard.ready || demoTransportArmed ? "positive-text" : ""}>
            {demo ? demoBridgeLabel : "—"}
          </strong>
        </article>
      </section>


      <section className="execution-panel" hidden={activeView !== "trading"}>
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">AUTOMATIC EXECUTION · ÉTAT BROKER</p>
            <h2>{automaticTradingLabel}</h2>
          </div>
          <span
            className={
              config?.live_trading_enabled || demoTransportArmed
                ? "badge gate-ready"
                : "badge gate-locked"
            }
          >
            {overview?.broker?.is_demo ? "BROKER DEMO" : "BROKER NON CONFIRMÉ"}
          </span>
        </div>

        <p className="execution-explainer">
          {demoTransportArmed
            ? "Le transport DEMO est armé. Un ordre ne part que si un PAPER sélectionné devient DEMO_COLLECTION / DEMO_ELIGIBLE et que tous les guards restent verts."
            : "Aucun ordre MT4 Trading-New ne peut partir actuellement : le runtime est en PAPER et le transport DEMO est désarmé. Les scanners et PAPER continuent à collecter les preuves."}
        </p>

        <div className="gate-grid">
          <div className="gate-card">
            <span className="label">Mode runtime</span>
            <strong>{config?.execution_mode.toUpperCase() ?? "—"}</strong>
            <p>Le mode PAPER simule les trades admissibles sans ordre broker.</p>
          </div>
          <div className="gate-card">
            <span className="label">Transport DEMO</span>
            <strong>{demoTransportArmed ? "ARMED" : "OFF"}</strong>
            <p>
              collection={config?.demo_collection_enabled ? "ON" : "OFF"} · bridge=
              {config?.demo_execution_bridge_enabled ? "ON" : "OFF"}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">PAPER ouverts</span>
            <strong>{openPaperRows.length}</strong>
            <p>{eligibleOpenPaperRows.length} ouvert(s) et PAPER-éligible(s).</p>
          </div>
          <div className="gate-card">
            <span className="label">Portfolio Manager</span>
            <strong>{overview?.portfolio.action.replaceAll("_", " ").toUpperCase() ?? "—"}</strong>
            <p>{overview?.portfolio.reason ?? "Décision indisponible."}</p>
          </div>
          <div className="gate-card">
            <span className="label">LIVE broker</span>
            <strong>{config?.live_trading_enabled ? "ACTIF" : "VERROUILLÉ"}</strong>
            <p>
              {overview?.portfolio.historical_active &&
              overview?.portfolio.prospective_supports_demo
                ? "Les preuves portefeuille sont présentes ; le flag LIVE reste un verrou séparé."
                : "Aucune stratégie n’a encore simultanément admission ACTIVE et preuve prospective SUPPORTS_DEMO."}
            </p>
          </div>
        </div>

        <div className="execution-path">
          <div className="execution-step">
            <span className={demoCollectionCandidates.length ? "step-dot step-ok" : "step-dot"} />
            <div>
              <strong>1 · Stratégie autorisée à la collecte DEMO</strong>
              <p>
                {demoCollectionCandidates.length} SHADOW PAPER-éligible(s) peuvent
                être mirrorés en DEMO ; {paperCandidates.length} mécanisme(s)
                peuvent ouvrir du PAPER au total.
              </p>
            </div>
          </div>
          <div className="execution-step">
            <span className={openDemoCollectionCandidates.length ? "step-dot step-ok" : "step-dot"} />
            <div>
              <strong>2 · Signal exécutable → PAPER collectable ouvert</strong>
              <p>
                {openDemoCollectionCandidates.length
                  ? "Un PAPER candidat à la collecte DEMO est ouvert."
                  : "Aucun PAPER candidat à la collecte DEMO n’est ouvert maintenant."}
              </p>
            </div>
          </div>
          <div className="execution-step">
            <span
              className={
                overview?.portfolio.action === "demo_collection" ||
                overview?.portfolio.action === "demo_eligible"
                  ? "step-dot step-ok"
                  : "step-dot"
              }
            />
            <div>
              <strong>3 · Portfolio sélectionne le trade</strong>
              <p>Le Portfolio Manager doit passer à DEMO_COLLECTION ou DEMO_ELIGIBLE.</p>
            </div>
          </div>
          <div className="execution-step">
            <span className={demoTransportArmed ? "step-dot step-ok" : "step-dot"} />
            <div>
              <strong>4 · Transport DEMO armé</strong>
              <p>Mode DEMO + collection ON + bridge ON, avec LIVE toujours OFF.</p>
            </div>
          </div>
          <div className="execution-step">
            <span className={demo?.guard.ready ? "step-dot step-ok" : "step-dot"} />
            <div>
              <strong>5 · Guards finaux</strong>
              <p>
                Broker DEMO confirmé, macro claire, budget journalier disponible,
                aucun ticket Trading-New déjà ouvert.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="manual-trade-panel" hidden={activeView !== "trading"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">MANUAL DEMO TRADE</p>
            <h2>Ouvrir un trade manuel avec les mêmes garde-fous</h2>
          </div>
          <p>
            Marché uniquement. Tu définis SL, TP et risque ; le système calcule le lot et refuse toute violation du contrat 400 €.
          </p>
        </div>

        <div className="manual-trade-grid">
          <label>
            <span>Actif</span>
            <select
              value={manualSymbol}
              onChange={(event) => { setManualSymbol(event.target.value); setManualPreview(null); }}
            >
              {retainedSymbols.map((symbol) => <option key={symbol}>{symbol}</option>)}
            </select>
          </label>
          <label>
            <span>Sens</span>
            <div className="manual-side-toggle">
              <button type="button" className={manualSide === "buy" ? "active" : ""} onClick={() => { setManualSide("buy"); setManualPreview(null); }}>BUY</button>
              <button type="button" className={manualSide === "sell" ? "active" : ""} onClick={() => { setManualSide("sell"); setManualPreview(null); }}>SELL</button>
            </div>
          </label>
          <label>
            <span>Stop loss</span>
            <input value={manualStop} onChange={(event) => { setManualStop(event.target.value); setManualPreview(null); }} inputMode="decimal" placeholder="Prix SL" />
          </label>
          <label>
            <span>Take profit</span>
            <input value={manualTarget} onChange={(event) => { setManualTarget(event.target.value); setManualPreview(null); }} inputMode="decimal" placeholder="Prix TP" />
          </label>
          <label>
            <span>Risque %</span>
            <input value={manualRiskPct} onChange={(event) => { setManualRiskPct(event.target.value); setManualPreview(null); }} inputMode="decimal" placeholder="1.0" />
            <small>1 % recommandé · 2 % maximum absolu</small>
          </label>
          <div className="manual-live-quote">
            <span>Cote broker live</span>
            <strong>{selectedManualQuote ? formatPrice(manualSide === "buy" ? selectedManualQuote.ask : selectedManualQuote.bid, selectedManualQuote.digits) : "—"}</strong>
            <small>{selectedManualQuote ? "spread " + formatPrice(selectedManualQuote.spread, selectedManualQuote.digits) + " · " + selectedManualQuote.status.toUpperCase() : "Cote indisponible"}</small>
          </div>
        </div>

        <div className="manual-actions">
          <button type="button" className="manual-preview-button" disabled={manualBusy || !demoTransportArmed} onClick={() => void previewManualTrade()}>
            {manualBusy ? "CALCUL…" : "PRÉVISUALISER"}
          </button>
          {manualPreview?.approved ? (
            <button type="button" className="manual-confirm-button" disabled={manualBusy} onClick={() => void submitManualTrade()}>
              CONFIRMER DEMO
            </button>
          ) : null}
        </div>

        {manualPreview ? (
          <div className={manualPreview.approved ? "manual-preview approved" : "manual-preview rejected"}>
            <div><span>Décision</span><strong>{manualPreview.approved ? "APPROUVÉ" : "REFUSÉ"}</strong></div>
            <div><span>Entrée marché</span><strong>{formatNumber(manualPreview.entry_price, selectedManualQuote?.digits ?? 5)}</strong></div>
            <div><span>Lot calculé</span><strong>{manualPreview.sizing ? manualPreview.sizing.lots.toFixed(2) : "—"}</strong></div>
            <div><span>Risque €</span><strong>{manualPreview.sizing ? manualPreview.sizing.expected_loss_eur.toFixed(2) + " €" : "—"}</strong></div>
            <div><span>Spread / stop</span><strong>{manualPreview.sizing ? (manualPreview.sizing.spread_to_stop * 100).toFixed(1) + " %" : "—"}</strong></div>
            <div><span>RR</span><strong>{manualPreview.reward_risk_ratio.toFixed(2)} R</strong></div>
            <div><span>Marge estimée</span><strong>{manualPreview.sizing ? manualPreview.sizing.estimated_margin_eur.toFixed(2) + " €" : "—"}</strong></div>
          </div>
        ) : null}

        {manualMessage ? <p className="manual-message">{manualMessage}</p> : null}
        <p className="manual-warning">DEMO uniquement. Le manuel est bloqué si un PAPER ou une position Trading-New est déjà ouvert. LIVE reste verrouillé.</p>
      </section>

      <section
        className="trade-blotter-panel"
        hidden={activeView !== "overview" && activeView !== "trading"}
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">TRADE BLOTTER</p>
            <h2>Positions et exécutions Trading-New</h2>
          </div>
          <p>Broker DEMO réel pour les positions bridge ; PAPER clairement séparé pour les simulations.</p>
        </div>

        <div className="blotter-group">
          <h3>Positions broker Trading-New</h3>
          {demo?.bridge_positions.length ? demo.bridge_positions.map((position) => (
            <div className="blotter-row" key={position.ticket}>
              <span className="badge gate-ready">{position.strategy_comment.startsWith("TradingNew:manual_demo:") ? "MANUAL DEMO" : "AUTO DEMO"}</span>
              <strong>{position.symbol} · {position.side.toUpperCase()}</strong>
              <span>{position.lots.toFixed(2)} lot</span>
              <span>entrée {position.open_price}</span>
              <span>SL {position.stop_loss}</span>
              <span>TP {position.take_profit}</span>
              <span className={position.profit >= 0 ? "positive" : "negative"}>{position.profit >= 0 ? "+" : ""}{position.profit.toFixed(2)} €</span>
              {position.strategy_comment.startsWith("TradingNew:manual_demo:") ? <button type="button" disabled={manualBusy} onClick={() => void closeManualTrade(position.ticket)}>FERMER</button> : null}
            </div>
          )) : <p className="strategy-empty">Aucune position Trading-New ouverte chez le broker.</p>}
        </div>

        <div className="blotter-group">
          <h3>PAPER ouverts</h3>
          {openPaperRows.length ? openPaperRows.map((row) => (
            <div className="blotter-row" key={row.strategy_id}>
              <span className="badge">PAPER</span>
              <strong>{row.symbol} · {row.summary.open_trade?.side.toUpperCase()}</strong>
              <span>{row.strategy_id}</span>
              <span>{row.summary.open_trade?.lots.toFixed(2)} lot</span>
              <span>SL {row.summary.open_trade?.stop_price}</span>
              <span>TP {row.summary.open_trade?.target_price}</span>
            </div>
          )) : <p className="strategy-empty">Aucun PAPER ouvert.</p>}
        </div>

        {demo?.pending_command ? <p className="manual-message">Commande broker en attente : {demo.pending_command.side.toUpperCase()} {demo.pending_command.symbol} {demo.pending_command.lots.toFixed(2)} lot.</p> : null}
        {demo?.latest_result ? <p className="manual-message">Dernier résultat bridge : {demo.latest_result.status.toUpperCase()} · ticket {demo.latest_result.ticket || "—"} · fill {demo.latest_result.fill_price || "—"}.</p> : null}

        {recentPaperTrades.length ? (
          <div className="paper-history">
            <div className="paper-row paper-row-head"><span>Signal</span><span>Stratégie</span><span>Side</span><span>Sortie</span><span>R</span></div>
            {recentPaperTrades.map(({ strategy_id, symbol, trade }) => (
              <div className="paper-row" key={strategy_id + trade.trade_id}>
                <span>{new Date(trade.signal_at).toLocaleString("fr-FR")}</span>
                <span>{symbol} · {strategy_id.split(":")[1]}</span>
                <span>{trade.side.toUpperCase()}</span>
                <span>{trade.status.toUpperCase()}</span>
                <span className={(trade.result_r ?? 0) >= 0 ? "positive" : "negative"}>{trade.result_r == null ? "—" : (trade.result_r >= 0 ? "+" : "") + trade.result_r.toFixed(2) + " R"}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="intelligence-panel" hidden={activeView !== "research"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">TRADING INTELLIGENCE · 8 CHANTIERS</p>
            <h2>Comprendre avant de modifier</h2>
          </div>
          <p>
            Snapshot read-only 24 h : trades/probes, mouvements market-first,
            attente, exécution broker, recherche par actif et qualification.
          </p>
        </div>

        <div className="intelligence-grid">
          <div className="intelligence-card">
            <span className="label">Mouvements market-first</span>
            <strong>{dailyReport?.market_opportunities_24h ?? "—"}</strong>
            <p>≥ {intelligence?.market_move_threshold_atr ?? 1.5} ATR sur {intelligence?.market_move_horizon_bars ?? 12} M5.</p>
          </div>
          <div className="intelligence-card">
            <span className="label">Capturés / manqués</span>
            <strong>
              {dailyReport
                ? dailyReport.captured_opportunities_24h + " / " + dailyReport.missed_opportunities_24h
                : "—"}
            </strong>
            <p>
              Capture{" "}
              {dailyReport && dailyReport.market_opportunities_24h
                ? ((dailyReport.captured_opportunities_24h / dailyReport.market_opportunities_24h) * 100).toFixed(1) + " %"
                : "—"}
            </p>
          </div>
          <div className="intelligence-card">
            <span className="label">PnL PAPER aujourd’hui</span>
            <strong className={(dailyReport?.paper_closed_pnl_eur_today ?? 0) >= 0 ? "positive-text" : "negative-text"}>
              {dailyReport
                ? (dailyReport.paper_closed_pnl_eur_today >= 0 ? "+" : "") +
                  dailyReport.paper_closed_pnl_eur_today.toFixed(2) +
                  " €"
                : "—"}
            </strong>
            <p>
              {dailyReport
                ? (dailyReport.paper_closed_r_today >= 0 ? "+" : "") +
                  dailyReport.paper_closed_r_today.toFixed(2) +
                  " R"
                : "—"}
            </p>
          </div>
          <div className="intelligence-card">
            <span className="label">Qualité exécution DEMO</span>
            <strong>{dailyReport?.execution_quality.fills ?? 0} fills</strong>
            <p>
              {dailyReport
                ? dailyReport.execution_quality.refused +
                  " refus · " +
                  dailyReport.execution_quality.errors +
                  " erreurs · slip " +
                  dailyReport.execution_quality.average_slippage_r.toFixed(3) +
                  "R"
                : "—"}
            </p>
          </div>
          <div className="intelligence-card">
            <span className="label">Qualification prospective</span>
            <strong>{dailyReport?.qualification_counts.supports_demo ?? 0} SUPPORTS_DEMO</strong>
            <p>
              {dailyReport?.qualification_counts.collecting ?? 0} collecting ·{" "}
              {dailyReport?.qualification_counts.failed ?? 0} failed
            </p>
          </div>
          <div className="intelligence-card">
            <span className="label">Broker réalisé</span>
            <strong>
              {dailyReport?.broker_realized_pnl_eur_today == null
                ? "UNKNOWN"
                : dailyReport.broker_realized_pnl_eur_today.toFixed(2) + " €"}
            </strong>
            <p>Le bridge actuel n’exporte pas encore le PnL réalisé des tickets fermés.</p>
          </div>
        </div>

        <div className="intelligence-subsection">
          <h3>Recherche et couverture par actif</h3>
          <div className="intelligence-table">
            <div className="intelligence-row intelligence-head">
              <span>Actif</span>
              <span>État</span>
              <span>Opp. 24 h</span>
              <span>Capturées</span>
              <span>Manquées</span>
              <span>Capture</span>
              <span>Exp. probes</span>
              <span>Prochaine action</span>
            </div>
            {(dailyReport?.assets ?? []).map((asset) => (
              <div className="intelligence-row" key={asset.symbol}>
                <strong>{asset.symbol}</strong>
                <span
                  className={
                    asset.state === "collect_prospective"
                      ? "positive-text"
                      : asset.state === "degraded"
                        ? "negative-text"
                        : ""
                  }
                >
                  {asset.state === "collect_prospective"
                    ? "COLLECT"
                    : asset.state === "degraded"
                      ? "DEGRADED"
                      : "RESEARCH"}
                </span>
                <span>{asset.market_opportunities_24h}</span>
                <span>{asset.captured_opportunities_24h}</span>
                <span>{asset.missed_opportunities_24h}</span>
                <span>{(asset.capture_rate_24h * 100).toFixed(1)} %</span>
                <span className={asset.blocked_expectancy_r_24h >= 0 ? "positive-text" : "negative-text"}>
                  {asset.blocked_expectancy_r_24h >= 0 ? "+" : ""}
                  {asset.blocked_expectancy_r_24h.toFixed(2)} R
                </span>
                <span>{asset.next_action}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="intelligence-subsection">
          <h3>Economic Feasibility Map · 400 €</h3>
          <p className="intelligence-note">
            Faisabilité d’exécution uniquement : même moteur de sizing, spread gelé, lot minimum,
            risque 1 % et marge 25 %. Une ligne INFEASIBLE n’autorise pas à augmenter le risque.
          </p>
          {economicFeasibility ? (
            <div className="intelligence-table economic-feasibility-table">
              <div className="intelligence-row economic-feasibility-row intelligence-head">
                <span>Actif</span>
                <span>Intervalle</span>
                <span>Stop min spread</span>
                <span>Stop max risque</span>
                <span>Capital min théorique</span>
                <span>Meilleur stop ATR</span>
                <span>Approbation hist.</span>
              </div>
              {economicFeasibility.assets.map((asset) => {
                const bestProfile = [...asset.stop_profiles].sort(
                  (left, right) => right.approval_rate - left.approval_rate
                )[0];
                return (
                  <div className="intelligence-row economic-feasibility-row" key={asset.symbol}>
                    <strong>{asset.symbol}</strong>
                    <span className={asset.feasible_stop_interval ? "positive-text" : "negative-text"}>
                      {asset.feasible_stop_interval ? "FEASIBLE" : "INFEASIBLE"}
                    </span>
                    <span>{asset.spread_stop_floor_price.toPrecision(4)}</span>
                    <span>{asset.risk_stop_ceiling_price.toPrecision(4)}</span>
                    <span>{asset.minimum_reference_capital_eur.toFixed(0)} €</span>
                    <span>{bestProfile ? bestProfile.stop_atr_multiple.toFixed(2) + " ATR" : "—"}</span>
                    <span>
                      {bestProfile ? (bestProfile.approval_rate * 100).toFixed(1) + " %" : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="strategy-empty">Snapshot économique non généré.</p>
          )}
        </div>

        <div className="intelligence-subsection">
          <h3>Patterns causaux observés au birth</h3>
          <p className="intelligence-note">
            Classification construite uniquement avec les barres disponibles au moment de la naissance
            de l’épisode. L’alignement compare ensuite cette direction causale au mouvement futur.
          </p>
          <div className="intelligence-table causal-pattern-table">
            <div className="intelligence-row causal-pattern-row intelligence-head">
              <span>Pattern</span>
              <span>Épisodes</span>
              <span>Manqués</span>
              <span>Alignés</span>
              <span>Opposés</span>
              <span>Neutres</span>
              <span>Move moyen</span>
            </div>
            {(intelligence?.causal_patterns ?? []).map((row) => (
              <div className="intelligence-row causal-pattern-row" key={row.pattern}>
                <strong>{row.pattern.replaceAll("_", " ")}</strong>
                <span>{row.episodes}</span>
                <span>{row.missed}</span>
                <span className={row.aligned > row.opposed ? "positive-text" : ""}>{row.aligned}</span>
                <span className={row.opposed > row.aligned ? "negative-text" : ""}>{row.opposed}</span>
                <span>{row.no_direction}</span>
                <span>{row.average_move_atr.toFixed(2)} ATR</span>
              </div>
            ))}
          </div>
        </div>

        <div className="intelligence-subsection">
          <h3>Missed Opportunity Review · plus gros mouvements non capturés</h3>
          <p className="intelligence-note">
            Télémétrie rétrospective uniquement : ces épisodes montrent où le marché a bougé
            sans signal SHADOW correspondant. Ils ne constituent pas des signaux de trading.
          </p>
          {topMissedOpportunities.length ? (
            <div className="intelligence-table missed-opportunity-table">
              <div className="intelligence-row missed-opportunity-row intelligence-head">
                <span>Naissance</span>
                <span>Actif</span>
                <span>Sens futur</span>
                <span>Mouvement</span>
                <span>Pattern causal</span>
                <span>Alignement</span>
                <span>Référence</span>
                <span>Horizon</span>
              </div>
              {topMissedOpportunities.map((episode) => (
                <div className="intelligence-row missed-opportunity-row" key={episode.episode_id}>
                  <span>{new Date(episode.birth_at).toLocaleString("fr-FR")}</span>
                  <strong>{episode.symbol}</strong>
                  <span className={episode.side === "buy" ? "positive-text" : "negative-text"}>
                    {episode.side.toUpperCase()}
                  </span>
                  <span>
                    <strong>{episode.move_atr.toFixed(2)} ATR</strong>
                  </span>
                  <span>{episode.causal_context.pattern.replaceAll("_", " ")}</span>
                  <span
                    className={
                      episode.causal_context.aligned_with_move === true
                        ? "positive-text"
                        : episode.causal_context.aligned_with_move === false
                          ? "negative-text"
                          : ""
                    }
                  >
                    {episode.causal_context.aligned_with_move === true
                      ? "ALIGNÉ"
                      : episode.causal_context.aligned_with_move === false
                        ? "OPPOSÉ"
                        : "NEUTRE"}
                  </span>
                  <span>{episode.reference_price}</span>
                  <span>{new Date(episode.horizon_end_at).toLocaleTimeString("fr-FR")}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="strategy-empty">Aucun épisode market-first manqué dans le snapshot.</p>
          )}
        </div>

        <div className="intelligence-subsection">
          <h3>Anatomie récente des trades / probes</h3>
          <div className="intelligence-table trade-intelligence-table">
            <div className="intelligence-row trade-intelligence-row intelligence-head">
              <span>Source</span>
              <span>Actif / mécanisme</span>
              <span>Résultat</span>
              <span>MFE</span>
              <span>MAE</span>
              <span>R perdu attente</span>
              <span>RR signal → entrée</span>
            </div>
            {(intelligence?.trades ?? []).slice(0, 10).map((trade) => (
              <div className="intelligence-row trade-intelligence-row" key={trade.trade_id}>
                <span>{trade.source === "paper" ? "PAPER" : "BLOCKED"}</span>
                <strong>{trade.symbol} · {trade.mechanism.replaceAll("_", " ")}</strong>
                <span className={(trade.result_r ?? 0) >= 0 ? "positive-text" : "negative-text"}>
                  {trade.result_r == null
                    ? trade.status.toUpperCase()
                    : (trade.result_r >= 0 ? "+" : "") + trade.result_r.toFixed(2) + " R"}
                </span>
                <span>{trade.mfe_r.toFixed(2)} R</span>
                <span>{trade.mae_r.toFixed(2)} R</span>
                <span className={trade.r_lost_while_waiting > 0 ? "negative-text" : "positive-text"}>
                  {trade.r_lost_while_waiting >= 0 ? "+" : ""}
                  {trade.r_lost_while_waiting.toFixed(2)} R
                </span>
                <span>
                  {trade.rr_at_signal == null ? "—" : trade.rr_at_signal.toFixed(2)}
                  {" → "}
                  {trade.rr_at_entry == null ? "—" : trade.rr_at_entry.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="intelligence-subsection">
          <h3>Historique qualification automatique</h3>
          {qualificationHistory.length ? (
            <div className="qualification-timeline">
              {qualificationHistory.slice(0, 10).map((event) => (
                <div className="qualification-event" key={event.strategy_id + event.at + event.closed_trades}>
                  <span className={"badge " + (event.state === "supports_demo" ? "gate-ready" : event.state === "failed" ? "gate-locked" : "")}>
                    {event.state.replaceAll("_", " ").toUpperCase()}
                  </span>
                  <strong>{event.strategy_id}</strong>
                  <span>{event.closed_trades} trades · E {event.expectancy_r >= 0 ? "+" : ""}{event.expectancy_r.toFixed(2)}R · PF {event.profit_factor.toFixed(2)} · DD {event.max_drawdown_r.toFixed(2)}R</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="strategy-empty">L’historique démarrera au prochain cycle du worker.</p>
          )}
        </div>

        {dailyReport?.limitations.length ? (
          <div className="intelligence-limitations">
            {dailyReport.limitations.map((item) => <p key={item}>• {item}</p>)}
          </div>
        ) : null}
      </section>

      <section className="strategy-map-panel" hidden={activeView !== "research"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">STRATEGY MAP · SPÉCIALISATION PAR ACTIF</p>
            <h2>Chaque actif ne doit pas trader la même chose</h2>
          </div>
          <p>
            Le moteur partage l’infrastructure, mais l’admission se fait par couple
            actif × mécanisme. Un mécanisme n’est collecté en PAPER que là où son
            évidence le justifie.
          </p>
        </div>
        <div className="strategy-map-grid">
          {strategyByAsset.map(({ symbol, eligible }) => (
            <article className="strategy-asset-card" key={symbol}>
              <div className="strategy-asset-head">
                <strong>{symbol}</strong>
                <span className={eligible.length ? "feed-status feed-live" : "feed-status feed-stale"}>
                  {eligible.length ? eligible.length + " PAPER" : "RESEARCH ONLY"}
                </span>
              </div>
              {eligible.length ? (
                <div className="strategy-list">
                  {eligible.map((row) => (
                    <div className="strategy-line" key={row.strategy_id}>
                      <strong>{row.mechanism.replaceAll("_", " ")}</strong>
                      <span>
                        {row.historical_state?.toUpperCase() ?? "—"} · weakest{" "}
                        {row.historical_weakest_expectancy_r == null
                          ? "—"
                          : (row.historical_weakest_expectancy_r >= 0 ? "+" : "") +
                            row.historical_weakest_expectancy_r.toFixed(3) +
                            "R"}
                      </span>
                      <span>
                        prospectif {row.summary.closed_trades}/{prospectiveTarget} ·{" "}
                        {row.qualification.state.replaceAll("_", " ")}
                        {row.historical_state === "shadow" && row.paper_entry_allowed
                          ? " · DEMO COLLECTABLE"
                          : ""}
                        {row.paper_collection_candidate ? " · UNDER-SAMPLED RULE" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="strategy-empty">
                  Aucun mécanisme PAPER-éligible actuellement. SHADOW continue à
                  chercher sans envoyer d’ordre.
                </p>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="gate-panel" hidden={activeView !== "trading"}>
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">ROAD TO BROKER DEMO · ÉTAT RÉEL</p>
            <h2>{demoRoadmapTitle}</h2>
          </div>
          <span className={`badge ${demo?.guard.ready ? "gate-ready" : "gate-locked"}`}>
            LIVE {config?.live_trading_enabled ? "ACTIF" : "VERROUILLÉ"}
          </span>
        </div>

        <div className="gate-grid">
          <div className="gate-card">
            <span className="label">Marchés runtime</span>
            <strong>{preflight ? `${preflight.ready_symbols.length}/5 READY` : "—"}</strong>
            <p>{preflight?.ready_symbols.join(", ") || "Préflight indisponible."}</p>
          </div>
          <div className="gate-card">
            <span className="label">Scanners SHADOW</span>
            <strong>{opportunities.length || "—"}</strong>
            <p>Détection causale active sur les cinq marchés conservés.</p>
          </div>
          <div className="gate-card">
            <span className="label">Candidats PAPER</span>
            <strong>{paperCandidates.length}</strong>
            <p>{paperCandidates.map((row) => row.strategy_id).join(" · ") || "Aucun candidat admis à la collecte."}</p>
          </div>
          <div className="gate-card">
            <span className="label">Preuve prospective</span>
            <strong>{prospectiveProgress}/{prospectiveTarget} trades</strong>
            <p>{bestProspective ? `Meilleure progression : ${bestProspective.strategy_id}` : "Aucune preuve prospective candidate clôturée."}</p>
          </div>
          <div className="gate-card">
            <span className="label">Admission historique</span>
            <strong>{overview?.portfolio.historical_active ? "ACTIVE" : "NON SATISFAITE"}</strong>
            <p>Politique actuelle : ≥{config?.historical_validation_min_trades ?? 40} validation + ≥{config?.historical_holdout_min_trades ?? 20} holdout.</p>
          </div>
          <div className="gate-card">
            <span className="label">Auto DEMO collection</span>
            <strong>{demoTransportArmed ? "ARMED" : "DISARMED"}</strong>
            <p>
              {demo?.collection_state?.paper_trade_id
                ? `${demo.collection_state.strategy_id ?? "—"} · ticket ${demo.collection_state.ticket ?? "en attente"}`
                : demoTransportArmed
                  ? demo?.collection_state?.last_error || "Armée, en attente d’un PAPER candidat exécutable."
                  : "Exécution broker désarmée ; SHADOW et PAPER continuent en observation."}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Isolation MT4</span>
            <strong>{demo ? `${demo.guard.bridge_open_positions} Trading-New` : "—"}</strong>
            <p>
              {demo
                ? `${demo.guard.broker_observed_positions} position(s) broker totale(s) · les positions externes ne sont jamais modifiées`
                : "Statut indisponible."}
            </p>
          </div>
        </div>
      </section>

      <section className="market-section" hidden={activeView !== "markets"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">MARKET FEED · MT4</p>
            <h2>Prix réels des actifs</h2>
          </div>
          <p>
            Rafraîchissement toutes les 5 secondes. Une cote ancienne est marquée STALE
            et n’est jamais présentée comme un prix temps réel.
          </p>
        </div>

        <div className="market-grid">
          {quotes.length ? (
            quotes.map((quote) => <MarketCard key={quote.symbol} quote={quote} />)
          ) : (
            <div className="empty-market">Flux MT4 indisponible.</div>
          )}
        </div>

        <div className="universe-table">
          <div className="universe-row universe-head">
            <span>Actif</span>
            <span>Prix / source</span>
            <span>M5/M15</span>
            <span>Spec</span>
            <span>Paper</span>
            <span>État</span>
          </div>
          {universe.map((asset) => (
            <div className="universe-row" key={asset.symbol}>
              <strong>{asset.symbol}</strong>
              <span>
                {asset.price.toLocaleString("fr-FR", { maximumFractionDigits: 5 })}
                <small>{asset.price_source === "broker_quote" ? " quote" : " close M5"}</small>
              </span>
              <span>{asset.has_m5 && asset.has_m15 ? "OK" : "INCOMPLET"}</span>
              <span>{asset.broker_spec_ready ? "OK" : "MANQUANTE"}</span>
              <span className={asset.paper_ready ? "positive" : ""}>
                {asset.paper_ready ? "READY" : "LOCK"}
              </span>
              <span className="universe-reason">{asset.reason}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="quality-panel" hidden={activeView !== "markets"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">CAPITAL / EXECUTION FEASIBILITY · 1 ATR M15</p>
            <h2>
              Quels marchés sont réellement tradables avec{" "}
              {config ? `${config.reference_capital_eur.toFixed(0)} €` : "—"} ?
            </h2>
          </div>
          <p>
            Référence structurelle, pas un signal : stop = 1 ATR M15 courant,
            granularité broker et spread observé.
          </p>
        </div>

        <div className="quality-table">
          <div className="quality-row quality-head">
            <span>Actif</span>
            <span>Score</span>
            <span>Spread / ATR</span>
            <span>Perte lot min</span>
            <span>Capital @1 %</span>
            <span>Capital @2 %</span>
            <span>
              Risque min / {config ? `${config.reference_capital_eur.toFixed(0)} €` : "—"}
            </span>
            <span>1 %</span>
            <span>2 %</span>
            <span>Research</span>
            <span>Diagnostic</span>
          </div>
          {marketQuality.map((row) => (
            <div className="quality-row" key={row.symbol}>
              <strong>{row.symbol}</strong>
              <span>{row.execution_quality_score.toFixed(0)}</span>
              <span>{(row.spread_atr_m15 * 100).toFixed(1)} %</span>
              <span>{row.min_lot_loss_atr_m15_eur.toFixed(2)} €</span>
              <span>{row.required_capital_base_risk_eur.toFixed(0)} €</span>
              <span>{row.required_capital_max_risk_eur.toFixed(0)} €</span>
              <span>{(row.minimum_feasible_risk_fraction * 100).toFixed(2)} %</span>
              <span className={row.default_risk_feasible ? "positive-text" : "negative-text"}>
                {row.default_risk_feasible ? "OK" : "NON"}
              </span>
              <span className={row.absolute_risk_feasible ? "positive-text" : "negative-text"}>
                {row.absolute_risk_feasible ? "OK" : "NON"}
              </span>
              <span className={row.eligible_for_m15_research ? "positive-text" : "negative-text"}>
                {row.eligible_for_m15_research ? "ELIGIBLE" : "LOCK"}
              </span>
              <span className="opportunity-reason">{row.reasons.join(" · ")}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="portfolio-panel" hidden={activeView !== "trading"}>
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">
              PORTFOLIO MANAGER ·{" "}
              {config ? `${config.reference_capital_eur.toFixed(0)} € ÉCONOMIQUES` : "—"}
            </p>
            <h2>{overview?.portfolio.action.replaceAll("_", " ").toUpperCase() ?? "—"}</h2>
          </div>
          <span className="badge">
            {overview?.portfolio.selected_strategy_id ?? "AUCUNE STRATÉGIE"}
          </span>
        </div>

        <div className="metric-grid">
          <div className="metric">
            <span>PnL recherche SHADOW</span>
            <strong>
              {overview
                ? `${overview.risk.research_paper_closed_pnl_eur >= 0 ? "+" : ""}${overview.risk.research_paper_closed_pnl_eur.toFixed(2)} €`
                : "—"}
            </strong>
          </div>
          <div className="metric">
            <span>Total R recherche</span>
            <strong>{overview ? `${overview.risk.research_paper_total_r.toFixed(2)} R` : "—"}</strong>
          </div>
          <div className="metric">
            <span>Risque SHADOW ouvert</span>
            <strong>{overview ? `${overview.risk.research_paper_open_risk_eur.toFixed(2)} €` : "—"}</strong>
          </div>
          <div className="metric">
            <span>PnL sélection aujourd'hui</span>
            <strong>{overview ? `${overview.risk.selected_daily_pnl_eur >= 0 ? "+" : ""}${overview.risk.selected_daily_pnl_eur.toFixed(2)} €` : "—"}</strong>
          </div>
          <div className="metric">
            <span>Budget perte journalier sélection</span>
            <strong>{overview ? `${overview.risk.remaining_daily_loss_budget_eur.toFixed(2)} €` : "—"}</strong>
          </div>
          <div className="metric">
            <span>Compte broker</span>
            <strong>{overview?.broker?.is_demo ? "DEMO" : "—"}</strong>
          </div>
          <div className="metric">
            <span>Positions broker observées</span>
            <strong>{overview?.broker?.observed_positions ?? "—"}</strong>
          </div>
        </div>

        <div className="decision-strip">
          <div>
            <span className="label">Décision portefeuille</span>
            <p>{overview?.portfolio.reason ?? "Indisponible"}</p>
          </div>
          <div>
            <span className="label">Solde broker DEMO observé</span>
            <p>
              {overview?.broker
                ? `${overview.broker.balance.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} € — ne pilote pas le sizing`
                : "Non disponible"}
            </p>
          </div>
        </div>

        <div className="strategy-table">
          <div className="strategy-row strategy-head">
            <span>Stratégie</span>
            <span>Trades</span>
            <span>Expectancy</span>
            <span>PF</span>
            <span>DD</span>
            <span>Historique</span>
            <span>Qualification</span>
          </div>
          {overview?.paper_strategies.length ? (
            overview.paper_strategies.map((row) => (
              <div className="strategy-row" key={row.strategy_id}>
                <strong>{row.strategy_id}</strong>
                <span>{row.summary.closed_trades}</span>
                <span>{row.summary.expectancy_r.toFixed(3)} R</span>
                <span>{row.summary.profit_factor.toFixed(2)}</span>
                <span>{row.summary.max_drawdown_r.toFixed(2)} R</span>
                <span>
                  {row.historical_state?.toUpperCase() ?? "—"}
                  {row.paper_entry_allowed ? " · PAPER ELIGIBLE" : ""}
                </span>
                <span>{row.qualification.state.replaceAll("_", " ").toUpperCase()}</span>
              </div>
            ))
          ) : (
            <div className="strategy-empty">Aucune preuve paper disponible pour le moment.</div>
          )}
        </div>

        <div className="cost-grid">
          {Object.entries(costs).map(([symbol, cost]) => (
            <div className="cost-card" key={symbol}>
              <strong>{symbol}</strong>
              <span>{cost.samples} mesures spread</span>
              <span>Moy. {cost.average_spread.toFixed(5)}</span>
              <span>Max {cost.max_spread.toFixed(5)}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="gate-panel" hidden={activeView !== "trading"}>
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">MACRO + EXECUTION GATE</p>
            <h2>{macro?.blocked ? "BLACKOUT MACRO" : "EXECUTION CONTROL"}</h2>
          </div>
          <span className={`badge ${demo?.guard.ready ? "gate-ready" : "gate-locked"}`}>
            {demo?.guard.ready ? "DEMO READY" : "DEMO LOCKED"}
          </span>
        </div>

        <div className="gate-grid">
          <div className="gate-card">
            <span className="label">Macro</span>
            <strong>{macro?.blocked ? "BLOCKED" : "CLEAR"}</strong>
            <p>{macro?.reason ?? "Calendrier macro indisponible."}</p>
          </div>
          <div className="gate-card">
            <span className="label">Prochain événement</span>
            <strong>{macro?.next_event?.name ?? "AUCUN"}</strong>
            <p>
              {macro?.next_event
                ? `${new Date(macro.next_event.start_at).toLocaleString("fr-FR")} · ${macro.next_event.source}`
                : "Aucun événement chargé."}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Exécution DEMO</span>
            <strong>{demo?.guard.execution_mode?.toUpperCase() ?? "—"}</strong>
            <p>
              {demo?.guard.ready
                ? "Tous les verrous sont satisfaits."
                : demo?.guard.reasons.join(" · ") || "Statut indisponible."}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Bridge MT4</span>
            <strong>{demo?.guard.bridge_enabled ? "ENABLED" : "DISABLED"}</strong>
            <p>
              {demo?.bridge_positions.length ?? 0} position(s) du bridge ·{" "}
              {demo?.pending_command
                ? "ouverture en attente"
                : demo?.pending_close_command
                  ? "fermeture en attente"
                  : "aucune commande"}
            </p>
          </div>
        </div>

        {demo?.latest_result ? (
          <div className="gate-result">
            <span>Dernier résultat bridge</span>
            <strong>{demo.latest_result.status.toUpperCase()}</strong>
            <span>
              ticket {demo.latest_result.ticket || "—"} · erreur {demo.latest_result.error_code}
            </span>
          </div>
        ) : null}
      </section>

      <section className="opportunity-panel" hidden={activeView !== "trading"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">LIVE OPPORTUNITY BOARD</p>
            <h2>{opportunities.length} scanners actifs</h2>
          </div>
          <p>
            Évaluation causale M5/M15. Aucun état SHADOW ne crée d’ordre broker.
          </p>
        </div>

        <div className="opportunity-summary">
          <span>
            EXECUTABLE <strong>{opportunities.filter((item) => item.state === "signal_executable").length}</strong>
          </span>
          <span>
            BLOQUÉ <strong>{opportunities.filter((item) => item.state === "signal_blocked").length}</strong>
          </span>
          <span>
            NO SIGNAL <strong>{opportunities.filter((item) => item.state === "no_signal").length}</strong>
          </span>
        </div>

        <div className="opportunity-table">
          <div className="opportunity-row opportunity-head">
            <span>Actif</span>
            <span>Mécanisme</span>
            <span>État</span>
            <span>Régime</span>
            <span>Side</span>
            <span>Dernière M5</span>
            <span>Diagnostic</span>
          </div>
          {opportunities.map((item) => (
            <div
              className="opportunity-row"
              key={`${item.symbol}:${item.mechanism}`}
            >
              <strong>{item.symbol}</strong>
              <span>{item.mechanism.replaceAll("_", " ")}</span>
              <span className={`opportunity-state state-${item.state}`}>
                {item.state.replaceAll("_", " ")}
              </span>
              <span>{item.regime.replaceAll("_", " ")}</span>
              <span>{item.side?.toUpperCase() ?? "—"}</span>
              <span>{new Date(item.latest_closed_m5_at).toLocaleTimeString("fr-FR")}</span>
              <span className="opportunity-reason">{item.reason}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="gate-panel" hidden={activeView !== "research"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">OPPORTUNITY FUNNEL · 24 H · READ-ONLY</p>
            <h2>Où meurent les opportunités</h2>
          </div>
          <p>
            Mesure les signaux détectés, les blocages économiques et le résultat
            contre-factuel des probes. Ce panneau ne change aucun seuil et ne crée
            aucun ordre.
          </p>
        </div>

        <div className="gate-grid">
          <div className="gate-card">
            <span className="label">Signaux détectés</span>
            <strong>{opportunityFunnel?.signal_rows ?? "—"}</strong>
            <p>
              {opportunityFunnel
                ? `${opportunityFunnel.blocked_signal_rows} bloqués · ${opportunityFunnel.executable_signal_rows} exécutables`
                : "Funnel indisponible."}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Probes bloqués</span>
            <strong>{opportunityFunnel?.tracked_blocked_probes ?? "—"}</strong>
            <p>
              {opportunityFunnel
                ? `${opportunityFunnel.resolved_blocked_probes} résolus · ${opportunityFunnel.open_blocked_probes} ouverts`
                : "—"}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Résultat contre-factuel</span>
            <strong
              className={
                opportunityFunnel
                  ? opportunityFunnel.blocked_total_r >= 0
                    ? "positive-text"
                    : "negative-text"
                  : ""
              }
            >
              {opportunityFunnel
                ? `${opportunityFunnel.blocked_total_r >= 0 ? "+" : ""}${opportunityFunnel.blocked_total_r.toFixed(2)} R`
                : "—"}
            </strong>
            <p>
              {opportunityFunnel
                ? `Expectancy ${opportunityFunnel.blocked_expectancy_r >= 0 ? "+" : ""}${opportunityFunnel.blocked_expectancy_r.toFixed(2)} R`
                : "—"}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Wins / losses bloqués</span>
            <strong>
              {opportunityFunnel
                ? `${opportunityFunnel.blocked_wins} / ${opportunityFunnel.blocked_losses}`
                : "—"}
            </strong>
            <p>Uniquement probes contre-factuels résolus.</p>
          </div>
          <div className="gate-card">
            <span className="label">Capital-limités faisables à 1 %</span>
            <strong>{opportunityFunnel?.capital_base_feasible_probes ?? "—"}</strong>
            <p>
              {opportunityFunnel
                ? `${opportunityFunnel.capital_base_feasible_resolved_probes} résolus · ${opportunityFunnel.capital_base_feasible_total_r >= 0 ? "+" : ""}${opportunityFunnel.capital_base_feasible_total_r.toFixed(2)} R · exp. ${opportunityFunnel.capital_base_feasible_expectancy_r >= 0 ? "+" : ""}${opportunityFunnel.capital_base_feasible_expectancy_r.toFixed(2)} R`
                : "—"}
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Capital-limités ≤ plafond 2 %</span>
            <strong>
              {opportunityFunnel
                ? `${opportunityFunnel.capital_max_feasible_probes}/${opportunityFunnel.capital_limited_probes}`
                : "—"}
            </strong>
            <p>
              Plafond absolu de{" "}
              {opportunityFunnel
                ? `${opportunityFunnel.absolute_max_risk_budget_eur.toFixed(2)} €`
                : "—"} ; jamais un sizing cible.
            </p>
          </div>
          <div className="gate-card">
            <span className="label">Blocages</span>
            <strong>{opportunityFunnel?.blocked_signal_rows ?? "—"}</strong>
            <p>
              {opportunityFunnel
                ? Object.entries(opportunityFunnel.block_reasons)
                    .map(([reason, count]) => `${count}× ${reason}`)
                    .join(" · ") || "Aucun blocage dans la fenêtre."
                : "—"}
            </p>
          </div>
        </div>

        {opportunityFunnel?.strategies.length ? (
          <div className="funnel-table">
            <div className="funnel-row funnel-head">
              <span>Stratégie</span>
              <span>Signaux</span>
              <span>Bloqués</span>
              <span>Exec.</span>
              <span>Probes</span>
              <span>Exp. bloquée</span>
              <span>Capital @1 %</span>
              <span>Fit @1 % maintenant</span>
              <span>R @1 % maintenant</span>
              <span>Blocage dominant</span>
            </div>
            {[...opportunityFunnel.strategies]
              .sort(
                (a, b) =>
                  b.signal_rows - a.signal_rows ||
                  b.tracked_blocked_probes - a.tracked_blocked_probes
              )
              .map((row) => {
                const dominantBlock = Object.entries(row.block_reasons).sort(
                  (a, b) => b[1] - a[1]
                )[0];
                const capitalRange =
                  row.min_required_capital_base_risk_eur == null
                    ? "—"
                    : row.max_required_capital_base_risk_eur == null ||
                        row.max_required_capital_base_risk_eur ===
                          row.min_required_capital_base_risk_eur
                      ? `${row.min_required_capital_base_risk_eur.toFixed(0)} €`
                      : `${row.min_required_capital_base_risk_eur.toFixed(0)}–${row.max_required_capital_base_risk_eur.toFixed(0)} €`;
                return (
                  <div className="funnel-row" key={row.strategy_id}>
                    <strong>
                      {row.symbol} · {row.mechanism.replaceAll("_", " ")}
                    </strong>
                    <span>{row.signal_rows}</span>
                    <span>{row.blocked_signal_rows}</span>
                    <span>{row.executable_signal_rows}</span>
                    <span>
                      {row.resolved_blocked_probes}
                      {row.open_blocked_probes ? ` +${row.open_blocked_probes} open` : ""}
                    </span>
                    <span
                      className={
                        row.resolved_blocked_probes
                          ? row.blocked_expectancy_r >= 0
                            ? "positive-text"
                            : "negative-text"
                          : ""
                      }
                    >
                      {row.resolved_blocked_probes
                        ? `${row.blocked_expectancy_r >= 0 ? "+" : ""}${row.blocked_expectancy_r.toFixed(2)} R`
                        : "—"}
                    </span>
                    <span>{capitalRange}</span>
                    <span>
                      {row.capital_base_feasible_probes
                        ? `${row.capital_base_feasible_probes}/${row.capital_limited_probes}`
                        : row.capital_limited_probes
                          ? `${0}/${row.capital_limited_probes}`
                          : "—"}
                    </span>
                    <span
                      className={
                        row.capital_base_feasible_resolved_probes
                          ? row.capital_base_feasible_total_r >= 0
                            ? "positive-text"
                            : "negative-text"
                          : ""
                      }
                    >
                      {row.capital_base_feasible_resolved_probes
                        ? `${row.capital_base_feasible_total_r >= 0 ? "+" : ""}${row.capital_base_feasible_total_r.toFixed(2)} R`
                        : "—"}
                    </span>
                    <span className="opportunity-reason">
                      {dominantBlock
                        ? `${dominantBlock[1]}× ${dominantBlock[0]}`
                        : "—"}
                    </span>
                  </div>
                );
              })}
          </div>
        ) : null}
      </section>

      <section className="blocked-probe-panel" hidden={activeView !== "research"}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">BLOCKED OPPORTUNITY PROBES</p>
            <h2>Edge bloqué ≠ edge perdu</h2>
          </div>
          <p>
            Suivi théorique en R des setups refusés par le sizing ou les coûts.
            Aucun lot ni ordre broker n’est créé.
          </p>
        </div>

        {blockedProbes.filter(
          (row) => row.summary.open_probe || row.summary.closed_probes > 0
        ).length ? (
          <div className="probe-table">
            <div className="probe-row probe-head">
              <span>Stratégie</span>
              <span>Probes</span>
              <span>Expectancy</span>
              <span>PF</span>
              <span>Ouvert</span>
              <span>Perte lot min</span>
              <span>Capital @1 %</span>
              <span>Capital @2 %</span>
              <span>Risque min</span>
              <span>Faisable ≤2 %</span>
              <span>Blocage</span>
            </div>
            {blockedProbes
              .filter(
                (row) => row.summary.open_probe || row.summary.closed_probes > 0
              )
              .map((row) => {
                const latest =
                  row.summary.open_probe ?? row.summary.recent_probes[0] ?? null;
                const currentMinimumRiskFraction =
                  latest && config
                    ? latest.min_lot_loss_eur / config.reference_capital_eur
                    : null;
                const currentMaxFeasible =
                  currentMinimumRiskFraction != null && config
                    ? currentMinimumRiskFraction <= config.absolute_max_risk_fraction
                    : null;
                return (
                  <div className="probe-row" key={row.strategy_id}>
                    <strong>{row.symbol} · {row.mechanism.replaceAll("_", " ")}</strong>
                    <span>{row.summary.closed_probes}</span>
                    <span className={row.summary.expectancy_r >= 0 ? "positive-text" : "negative-text"}>
                      {row.summary.closed_probes
                        ? `${row.summary.expectancy_r >= 0 ? "+" : ""}${row.summary.expectancy_r.toFixed(2)} R`
                        : "—"}
                    </span>
                    <span>{row.summary.closed_probes ? row.summary.profit_factor.toFixed(2) : "—"}</span>
                    <span>{row.summary.open_probe ? row.summary.open_probe.side.toUpperCase() : "—"}</span>
                    <span>{latest ? `${latest.min_lot_loss_eur.toFixed(2)} €` : "—"}</span>
                    <span>{latest ? `${latest.required_capital_base_risk_eur.toFixed(0)} €` : "—"}</span>
                    <span>{latest ? `${latest.required_capital_max_risk_eur.toFixed(0)} €` : "—"}</span>
                    <span>
                      {currentMinimumRiskFraction != null
                        ? `${(currentMinimumRiskFraction * 100).toFixed(2)} %`
                        : "—"}
                    </span>
                    <span
                      className={
                        currentMaxFeasible == null
                          ? ""
                          : currentMaxFeasible
                            ? "positive-text"
                            : "negative-text"
                      }
                    >
                      {currentMaxFeasible == null ? "—" : currentMaxFeasible ? "OUI" : "NON"}
                    </span>
                    <span className="opportunity-reason">{latest?.block_reason ?? "—"}</span>
                  </div>
                );
              })}
          </div>
        ) : (
          <p className="paper-empty">
            Aucun probe bloqué suivi depuis l’activation de cette télémétrie.
          </p>
        )}
      </section>

      <section className="shadow-panel" hidden={activeView !== "research"}>
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">BTCUSD · BREAK / RETEST · SHADOW</p>
            <h2>{stateLabel(shadow?.state)}</h2>
          </div>
          <span className={`badge badge-${shadow?.state ?? "unknown"}`}>
            {shadow?.side?.toUpperCase() ?? shadow?.regime ?? "—"}
          </span>
        </div>

        <div className="metric-grid">
          <div className="metric">
            <span>Régime M15</span>
            <strong>{shadow?.regime ?? "—"}</strong>
          </div>
          <div className="metric">
            <span>Volatilité percentile</span>
            <strong>
              {shadow ? `${(shadow.volatility_percentile * 100).toFixed(0)}e` : "—"}
            </strong>
          </div>
          <div className="metric">
            <span>Momentum 12 M15</span>
            <strong>{formatNumber(shadow?.momentum_12_atr)} ATR</strong>
          </div>
          <div className="metric">
            <span>Efficacité directionnelle</span>
            <strong>{formatNumber(shadow?.efficiency)}</strong>
          </div>
          <div className="metric">
            <span>ATR M15</span>
            <strong>{formatNumber(shadow?.atr_m15)}</strong>
          </div>
          <div className="metric">
            <span>Dernière M5 fermée</span>
            <strong className="small">
              {shadow ? new Date(shadow.latest_closed_m5_at).toLocaleString("fr-FR") : "—"}
            </strong>
          </div>
        </div>

        <div className="decision-strip">
          <div>
            <span className="label">Diagnostic</span>
            <p>{shadow?.reason ?? "Scanner SHADOW indisponible."}</p>
          </div>
          <div>
            <span className="label">Sizing 1 %</span>
            <p>
              {shadow?.base_risk
                ? shadow.base_risk.approved
                  ? `${shadow.base_risk.lots.toFixed(2)} lot · risque ${shadow.base_risk.expected_loss_eur.toFixed(2)} €`
                  : shadow.base_risk.reason
                : "Aucun signal à dimensionner"}
            </p>
          </div>
        </div>
      </section>

      <section className="paper-panel" hidden={activeView !== "research"}>
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">PROSPECTIVE PAPER EVIDENCE · BTCUSD</p>
            <h2>{paper?.open_trade ? "TRADE PAPER OUVERT" : "SUIVI PROSPECTIF"}</h2>
          </div>
          <span className="badge">
            {paper ? `${paper.closed_trades} clôturé${paper.closed_trades > 1 ? "s" : ""}` : "—"}
          </span>
        </div>

        <div className="metric-grid">
          <div className="metric">
            <span>Expectancy</span>
            <strong>{paper ? `${paper.expectancy_r >= 0 ? "+" : ""}${paper.expectancy_r.toFixed(3)} R` : "—"}</strong>
          </div>
          <div className="metric">
            <span>Profit factor</span>
            <strong>{paper ? paper.profit_factor.toFixed(2) : "—"}</strong>
          </div>
          <div className="metric">
            <span>Total R</span>
            <strong>{paper ? `${paper.total_r >= 0 ? "+" : ""}${paper.total_r.toFixed(2)} R` : "—"}</strong>
          </div>
          <div className="metric">
            <span>PnL paper</span>
            <strong>{paper ? `${paper.total_pnl_eur >= 0 ? "+" : ""}${paper.total_pnl_eur.toFixed(2)} €` : "—"}</strong>
          </div>
          <div className="metric">
            <span>Legacy pré-cutover</span>
            <strong>
              {paper
                ? `${paper.legacy_trades} trades · ${paper.legacy_total_r.toFixed(2)} R`
                : "—"}
            </strong>
          </div>
          <div className="metric">
            <span>Gagnants / perdants</span>
            <strong>{paper ? `${paper.wins} / ${paper.losses}` : "—"}</strong>
          </div>
          <div className="metric">
            <span>Win rate</span>
            <strong>
              {paper && paper.closed_trades
                ? `${((paper.wins / paper.closed_trades) * 100).toFixed(0)} %`
                : "—"}
            </strong>
          </div>
        </div>

        {paper?.open_trade ? (
          <div className="paper-open">
            <div>
              <span className="label">Position paper</span>
              <strong>{paper.open_trade.side.toUpperCase()} · {paper.open_trade.lots.toFixed(2)} lot</strong>
            </div>
            <div>
              <span>Entrée</span>
              <strong>{paper.open_trade.entry_price.toFixed(2)}</strong>
            </div>
            <div>
              <span>Stop</span>
              <strong>{paper.open_trade.stop_price.toFixed(2)}</strong>
            </div>
            <div>
              <span>Target</span>
              <strong>{paper.open_trade.target_price.toFixed(2)}</strong>
            </div>
            <div>
              <span>Risque</span>
              <strong>{paper.open_trade.risk_eur.toFixed(2)} €</strong>
            </div>
          </div>
        ) : (
          <p className="paper-empty">
            Aucun trade paper ouvert. Le système attend un signal exécutable à 1 % de risque.
          </p>
        )}

        {paper?.recent_trades.length ? (
          <div className="paper-history">
            <div className="paper-row paper-row-head">
              <span>Signal</span>
              <span>Side</span>
              <span>Sortie</span>
              <span>R</span>
              <span>PnL</span>
            </div>
            {paper.recent_trades.map((trade) => (
              <div className="paper-row" key={trade.trade_id}>
                <span>{new Date(trade.signal_at).toLocaleString("fr-FR")}</span>
                <span>{trade.side.toUpperCase()}</span>
                <span>{trade.status.toUpperCase()}</span>
                <span className={(trade.result_r ?? 0) >= 0 ? "positive" : "negative"}>
                  {trade.result_r == null
                    ? "—"
                    : `${trade.result_r >= 0 ? "+" : ""}${trade.result_r.toFixed(2)} R`}
                </span>
                <span className={(trade.pnl_eur ?? 0) >= 0 ? "positive" : "negative"}>
                  {trade.pnl_eur == null
                    ? "—"
                    : `${trade.pnl_eur >= 0 ? "+" : ""}${trade.pnl_eur.toFixed(2)} €`}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel" hidden={activeView !== "research"}>
        <div>
          <p className="eyebrow">STRATEGY ADMISSION</p>
          <h2>REJECTED → SHADOW → ACTIVE</h2>
        </div>
        <p>
          Les opportunités sont observées prospectivement avant activation. Un
          signal SHADOW n’est pas un ordre et ne contourne aucun garde-fou.
        </p>
      </section>
    </main>
  );
}

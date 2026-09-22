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
  paper_collection_candidate: boolean;
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
    profit: number;
  }[];
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
  min_required_capital_base_risk_eur: number | null;
  max_required_capital_base_risk_eur: number | null;
  block_reasons: Record<string, number>;
};

type OpportunityFunnel = {
  window_hours: number;
  window_start: string;
  window_end: string;
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
  block_reasons: Record<string, number>;
  strategies: OpportunityFunnelStrategy[];
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
          opportunityFunnelResponse
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
          fetch("/api/v1/shadow/opportunity-funnel?hours=24")
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
    (row) => row.paper_collection_candidate
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

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">M5 / M15 · MT4 · REGIME-FIRST</p>
        <h1>Trading Control Center</h1>
        <p className="subtitle">
          Marché réel MT4, détection de régime et collecte SHADOW dans une vue unique.
          Le live trading reste verrouillé tant qu’aucune stratégie n’est qualifiée.
        </p>
      </header>

      <section className={`preflight-panel preflight-${preflight?.status ?? "unknown"}`}>
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
        ) : null}
      </section>

      <section className="grid">
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


      <section className="gate-panel">
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

      <section className="market-section">
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

      <section className="quality-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CAPITAL / EXECUTION FEASIBILITY · 1 ATR M15</p>
            <h2>Quels marchés sont réellement tradables avec 200 € ?</h2>
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
            <span>Risque min / 200 €</span>
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

      <section className="portfolio-panel">
        <div className="shadow-heading">
          <div>
            <p className="eyebrow">PORTFOLIO MANAGER · 200 € ÉCONOMIQUES</p>
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
                <span>{row.historical_state?.toUpperCase() ?? "—"}{row.paper_collection_candidate ? " · PAPER CANDIDATE" : ""}</span>
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

      <section className="gate-panel">
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

      <section className="opportunity-panel">
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

      <section className="gate-panel">
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
            <span className="label">Faisables sous plafond 2 %</span>
            <strong>{opportunityFunnel?.blocked_feasible_under_max_risk ?? "—"}</strong>
            <p>
              Le plafond 2 % reste une limite absolue, pas un sizing cible.
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

      <section className="blocked-probe-panel">
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
                    <span>{latest ? `${(latest.minimum_feasible_risk_fraction * 100).toFixed(2)} %` : "—"}</span>
                    <span className={latest?.capital_granularity_feasible_under_max_risk ? "positive-text" : "negative-text"}>
                      {latest ? (latest.capital_granularity_feasible_under_max_risk ? "OUI" : "NON") : "—"}
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

      <section className="shadow-panel">
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

      <section className="paper-panel">
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

      <section className="panel">
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

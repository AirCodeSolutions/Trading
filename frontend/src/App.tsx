import { useEffect, useMemo, useState } from "react";

type RuntimeConfig = {
  execution_mode: string;
  decision_mode: string;
  live_trading_enabled: boolean;
  allowed_timeframes: string[];
  reference_capital_eur: number;
  risk_per_trade_fraction: number;
  absolute_max_risk_fraction: number;
};

type ShadowSizing = {
  approved: boolean;
  reason: string;
  lots: number;
  expected_loss_eur: number;
  spread_to_stop: number;
};

type ShadowDiagnostic = {
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
    action: "no_trade" | "paper_only" | "demo_eligible";
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
    portfolio_action: "no_trade" | "paper_only" | "demo_eligible";
    macro_blocked: boolean;
    reasons: string[];
  };
  pending_command: {
    command_id: string;
    symbol: string;
    side: "buy" | "sell";
    lots: number;
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
  status: "ready" | "waiting_market" | "degraded" | "blocked";
  worker_ok: boolean;
  worker_age_seconds: number | null;
  macro_blocked: boolean;
  portfolio_action: string;
  demo_execution_ready: boolean;
  ready_symbols: string[];
  waiting_symbols: string[];
  degraded_symbols: string[];
  assets: {
    symbol: string;
    state: "ready" | "waiting_quote" | "missing_spec" | "missing_history";
    quote_live: boolean;
    paper_ready: boolean;
    broker_spec_ready: boolean;
    has_m5: boolean;
    has_m15: boolean;
    reason: string;
  }[];
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
  const [paper, setPaper] = useState<PaperSummary | null>(null);
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [universe, setUniverse] = useState<MarketUniverseAsset[]>([]);
  const [overview, setOverview] = useState<TradingOverview | null>(null);
  const [costs, setCosts] = useState<CostSummary>({});
  const [macro, setMacro] = useState<MacroStatus | null>(null);
  const [demo, setDemo] = useState<DemoExecutionStatus | null>(null);
  const [preflight, setPreflight] = useState<SessionPreflight | null>(null);
  const [status, setStatus] = useState("Connexion au backend…");

  useEffect(() => {
    let active = true;

    const refreshCore = async () => {
      try {
        const [
          healthResponse,
          configResponse,
          shadowResponse,
          paperResponse,
          universeResponse,
          overviewResponse,
          costsResponse,
          macroResponse,
          demoResponse,
          preflightResponse
        ] = await Promise.all([
          fetch("/api/v1/health"),
          fetch("/api/v1/config"),
          fetch("/api/v1/shadow/mt4/btc/break-retest"),
          fetch("/api/v1/shadow/mt4/btc/break-retest/paper"),
          fetch("/api/v1/market/mt4/universe"),
          fetch("/api/v1/portfolio/overview"),
          fetch("/api/v1/market/mt4/costs"),
          fetch("/api/v1/macro/status"),
          fetch("/api/v1/execution/demo/status"),
          fetch("/api/v1/session/preflight")
        ]);
        if (!healthResponse.ok || !configResponse.ok) {
          throw new Error("backend unavailable");
        }

        const health = await healthResponse.json();
        const runtime = await configResponse.json();
        const shadowPayload = shadowResponse.ok ? await shadowResponse.json() : null;
        const paperPayload = paperResponse.ok ? await paperResponse.json() : null;
        const universePayload = universeResponse.ok ? await universeResponse.json() : [];
        const overviewPayload = overviewResponse.ok ? await overviewResponse.json() : null;
        const costsPayload = costsResponse.ok ? await costsResponse.json() : {};
        const macroPayload = macroResponse.ok ? await macroResponse.json() : null;
        const demoPayload = demoResponse.ok ? await demoResponse.json() : null;
        const preflightPayload = preflightResponse.ok
          ? await preflightResponse.json()
          : null;

        if (!active) return;
        setStatus(health.status === "ok" ? "Opérationnel" : "Dégradé");
        setConfig(runtime);
        setShadow(shadowPayload);
        setPaper(paperPayload);
        setUniverse(universePayload);
        setOverview(overviewPayload);
        setCosts(costsPayload);
        setMacro(macroPayload);
        setDemo(demoPayload);
        setPreflight(preflightPayload);
      } catch {
        if (active) setStatus("Backend indisponible");
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

    const refreshQuotes = async () => {
      try {
        const response = await fetch("/api/v1/market/mt4/live");
        if (!response.ok) throw new Error("market feed unavailable");
        const payload = (await response.json()) as MarketQuote[];
        if (active) setQuotes(payload);
      } catch {
        if (active) setQuotes([]);
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
          <span className="label">PnL recherche SHADOW</span>
          <strong>
            {overview
              ? `${overview.risk.research_paper_closed_pnl_eur >= 0 ? "+" : ""}${overview.risk.research_paper_closed_pnl_eur.toFixed(2)} €`
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
          <strong className={demo?.guard.ready ? "positive-text" : ""}>
            {demo ? (demo.guard.ready ? "READY" : "LOCKED") : "—"}
          </strong>
        </article>
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
              {demo?.pending_command ? "commande en attente" : "aucune commande"}
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

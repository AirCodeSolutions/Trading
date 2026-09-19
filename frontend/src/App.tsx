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
  const [status, setStatus] = useState("Connexion au backend…");

  useEffect(() => {
    let active = true;

    const refreshCore = async () => {
      try {
        const [healthResponse, configResponse, shadowResponse, paperResponse] =
          await Promise.all([
            fetch("/api/v1/health"),
            fetch("/api/v1/config"),
            fetch("/api/v1/shadow/mt4/btc/break-retest"),
            fetch("/api/v1/shadow/mt4/btc/break-retest/paper")
          ]);
        if (!healthResponse.ok || !configResponse.ok) {
          throw new Error("backend unavailable");
        }

        const health = await healthResponse.json();
        const runtime = await configResponse.json();
        const shadowPayload = shadowResponse.ok ? await shadowResponse.json() : null;
        const paperPayload = paperResponse.ok ? await paperResponse.json() : null;

        if (!active) return;
        setStatus(health.status === "ok" ? "Opérationnel" : "Dégradé");
        setConfig(runtime);
        setShadow(shadowPayload);
        setPaper(paperPayload);
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
          <span className="label">Environnement</span>
          <strong>{config?.execution_mode ?? "—"}</strong>
        </article>
        <article className="card">
          <span className="label">Capital référence</span>
          <strong>{config ? `${config.reference_capital_eur.toFixed(0)} €` : "—"}</strong>
        </article>
        <article className="card">
          <span className="label">Risque base / trade</span>
          <strong>
            {config ? `${(config.risk_per_trade_fraction * 100).toFixed(1)} %` : "—"}
          </strong>
        </article>
        <article className="card">
          <span className="label">Live trading</span>
          <strong>{config?.live_trading_enabled ? "ACTIF" : "VERROUILLÉ"}</strong>
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

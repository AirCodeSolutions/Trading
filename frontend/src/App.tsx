import { useEffect, useState } from "react";

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

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? "—" : value.toFixed(digits);
}

function stateLabel(state: ShadowDiagnostic["state"] | undefined) {
  if (state === "signal_executable") return "SIGNAL EXÉCUTABLE";
  if (state === "signal_blocked") return "SIGNAL BLOQUÉ";
  if (state === "no_signal") return "NO SIGNAL";
  return "—";
}

export default function App() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [shadow, setShadow] = useState<ShadowDiagnostic | null>(null);
  const [status, setStatus] = useState("Connexion au backend…");

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      try {
        const [healthResponse, configResponse, shadowResponse] = await Promise.all([
          fetch("/api/v1/health"),
          fetch("/api/v1/config"),
          fetch("/api/v1/shadow/mt4/btc/break-retest")
        ]);
        if (!healthResponse.ok || !configResponse.ok) {
          throw new Error("backend unavailable");
        }

        const health = await healthResponse.json();
        const runtime = await configResponse.json();
        const shadowPayload = shadowResponse.ok ? await shadowResponse.json() : null;

        if (!active) return;
        setStatus(health.status === "ok" ? "Opérationnel" : "Dégradé");
        setConfig(runtime);
        setShadow(shadowPayload);
      } catch {
        if (active) setStatus("Backend indisponible");
      }
    };

    void refresh();
    const timer = window.setInterval(refresh, 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">M5 / M15 · MT4 · REGIME-FIRST</p>
        <h1>Trading Control Center</h1>
        <p className="subtitle">
          Le système cherche l’edge avant de chercher le trade. Le live reste
          verrouillé tant qu’aucune stratégie n’est qualifiée.
        </p>
      </header>

      <section className="grid">
        <article className="card">
          <span className="label">Système</span>
          <strong>{status}</strong>
        </article>
        <article className="card">
          <span className="label">Environnement</span>
          <strong>{config?.execution_mode ?? "—"}</strong>
        </article>
        <article className="card">
          <span className="label">Décision</span>
          <strong>{config?.decision_mode ?? "—"}</strong>
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

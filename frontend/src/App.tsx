import { useEffect, useState } from "react";

type RuntimeConfig = {
  execution_mode: string;
  live_trading_enabled: boolean;
  allowed_timeframes: string[];
  reference_capital_eur: number;
  risk_per_trade_fraction: number;
  absolute_max_risk_fraction: number;
};

export default function App() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [status, setStatus] = useState("Connexion au backend…");

  useEffect(() => {
    Promise.all([
      fetch("/api/v1/health").then((response) => response.json()),
      fetch("/api/v1/config").then((response) => response.json())
    ])
      .then(([health, runtime]) => {
        setStatus(health.status === "ok" ? "Opérationnel" : "Dégradé");
        setConfig(runtime);
      })
      .catch(() => setStatus("Backend indisponible"));
  }, []);

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">M5 / M15 · MT4 · CAPITAL-AWARE</p>
        <h1>Trading Control Center</h1>
        <p className="subtitle">
          Le moteur sélectionne un marché seulement si le coût d’exécution,
          le stop et le lot minimum sont compatibles avec le capital de référence.
        </p>
      </header>

      <section className="grid">
        <article className="card">
          <span className="label">Système</span>
          <strong>{status}</strong>
        </article>
        <article className="card">
          <span className="label">Mode</span>
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
          <span className="label">Plafond absolu / trade</span>
          <strong>
            {config ? `${(config.absolute_max_risk_fraction * 100).toFixed(1)} %` : "—"}
          </strong>
        </article>
        <article className="card">
          <span className="label">Live trading</span>
          <strong>{config?.live_trading_enabled ? "ACTIF" : "VERROUILLÉ"}</strong>
        </article>
      </section>

      <section className="panel">
        <div>
          <p className="eyebrow">MARKET SELECTOR</p>
          <h2>Le marché doit mériter le trade.</h2>
        </div>
        <p>
          Les prochains écrans classeront les instruments MT4 par coût relatif,
          granularité du lot, régime M15 et edge historique walk-forward avant
          qu’une stratégie M5 soit autorisée à entrer.
        </p>
      </section>
    </main>
  );
}

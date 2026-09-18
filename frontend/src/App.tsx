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
        <p className="eyebrow">M5 / M15 · MT4 · REGIME-FIRST</p>
        <h1>Trading Control Center</h1>
        <p className="subtitle">
          M15 décide du contexte. M5 cherche l’entrée. Une stratégie ne peut
          devenir active qu’après validation indépendante et contrôle des coûts.
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
          <p className="eyebrow">STRATEGY ADMISSION</p>
          <h2>REJECTED → SHADOW → ACTIVE</h2>
        </div>
        <p>
          Le moteur de replay historique et le runtime utilisent le même chemin
          causal. Le mode CONFIRM garde la validation humaine ; le mode AUTO
          autorise directement une proposition qualifiée, sans contourner les
          garde-fous de risque.
        </p>
      </section>
    </main>
  );
}

import { useEffect, useState } from "react";

type RuntimeConfig = {
  execution_mode: string;
  live_trading_enabled: boolean;
  allowed_timeframes: string[];
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
        <p className="eyebrow">M5 / M15 TRADING ENGINE</p>
        <h1>Trading Control Center</h1>
        <p className="subtitle">
          Données de marché, décisions, risque et exécution dans une seule interface.
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
          <span className="label">Timeframes</span>
          <strong>{config?.allowed_timeframes.join(" · ") ?? "—"}</strong>
        </article>
        <article className="card">
          <span className="label">Live trading</span>
          <strong>{config?.live_trading_enabled ? "ACTIF" : "VERROUILLÉ"}</strong>
        </article>
      </section>

      <section className="panel">
        <div>
          <p className="eyebrow">PROCHAINE ÉTAPE</p>
          <h2>Brancher le flux de marché et le broker</h2>
        </div>
        <p>
          Le socle accepte déjà des bougies M5/M15. Le connecteur de données,
          le moteur de stratégie et l’adaptateur d’exécution seront branchés
          sans coupler la logique de trading au broker.
        </p>
      </section>
    </main>
  );
}

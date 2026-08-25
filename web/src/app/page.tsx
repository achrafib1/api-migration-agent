import { MigrationConsole } from "@/components/migration-console";

export default function Home() {
  return (
    <main className="site-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="API Migration Agent home">
          <span className="brand-mark">AM</span>
          <span>API Migration Agent</span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#workflow">Workflow</a>
          <a href="#safety">Safety</a>
          <a href="http://localhost:8000/docs">API docs</a>
        </nav>
        <span className="version-pill">MVP · Local</span>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span /> Evidence-first migration engineering</p>
          <h1>API changes,<br /><em>handled with proof.</em></h1>
          <p className="hero-lede">
            Turn verified OpenAPI changes into a human-approved Python client migration—then
            validate every patch inside an isolated workspace.
          </p>
          <div className="trust-row" id="safety">
            <span>Deterministic diff</span>
            <span>Human approval</span>
            <span>Fixed validation</span>
          </div>
        </div>
        <aside className="hero-aside">
          <span className="aside-index">01</span>
          <p>Built for reviewability</p>
          <blockquote>“The model proposes. Evidence and people decide.”</blockquote>
        </aside>
      </section>

      <div id="workflow">
        <MigrationConsole />
      </div>

      <footer>
        <span>API Migration Agent</span>
        <span>Local-first · Evidence-backed · Human-controlled</span>
      </footer>
    </main>
  );
}

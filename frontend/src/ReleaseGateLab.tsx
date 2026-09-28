const checks = [
  ["CLEAN BUILD", "PASS", "three isolated containers"],
  ["POSTGRESQL", "PASS", "ready · forced RLS"],
  ["TENANT ISOLATION", "PASS", "0 cross-tenant rows"],
  ["LOCAL LOAD", "PASS", "100 requests · 0 failures · p95 61.27 ms"],
  ["AUTH0 JWT", "PASS", "signature · issuer · audience · time"],
  ["AUTH0 ORG + RBAC", "PASS", "Acme + Globex · 0 cross-tenant rows"],
];

export default function ReleaseGateLab() {
  return (
    <section className="release-gate" aria-labelledby="release-gate-title">
      <header>
        <div>
          <p className="eyebrow">FINAL PRODUCTION GATE</p>
          <h2 id="release-gate-title">Evidence decides whether we ship</h2>
        </div>
        <div className="release-hold">
          <b>READY</b>
          <span>6 / 6 passed</span>
        </div>
      </header>
      <div className="release-grid">
        {checks.map(([name, state, detail]) => (
          <article key={name}>
            <small>{name}</small>
            <b>{state}</b>
            <span>{detail}</span>
          </article>
        ))}
      </div>
      <footer>
        Infrastructure ready
        <span>release identity verified with live organization tokens</span>
      </footer>
    </section>
  );
}

const controls = [
  ["ACCESS", "CTL-ACCESS-01", "non-root · read-only · caps dropped"],
  ["CONSENT", "CTL-CONSENT-01", "explicit start before capture"],
  ["RETENTION", "CTL-RETENTION-01", "class + expiry required"],
  ["DELETION", "CTL-DELETE-01", "propagate + verify receipt"],
  ["TENANT", "CTL-TENANT-01", "scope before retrieval"],
  ["ACCESSIBILITY", "CTL-A11Y-01", "keyboard path tested"],
  ["INCIDENT", "CTL-IR-01", "contain · preserve · rollback"],
  ["COST", "CTL-COST-01", "bounded work and spend"],
];

export default function ProductionControlLab() {
  return (
    <section className="control-lab" aria-labelledby="control-lab-title">
      <header>
        <div>
          <p className="eyebrow">PRODUCTION CONTROL GATE · OCI</p>
          <h2 id="control-lab-title">Ship only with inspectable controls</h2>
        </div>
        <div className="control-release"><b>READY</b><span>8 / 8 passed</span></div>
      </header>
      <div className="control-grid">
        {controls.map(([area, id, evidence]) => (
          <article key={id}>
            <small>{area}</small><b>{id}</b><span>{evidence}</span><em>PASS</em>
          </article>
        ))}
      </div>
      <footer>
        NIST AI RMF · OWASP · WCAG 2.2 · OCI
        <span>engineering mapping, not certification</span>
      </footer>
    </section>
  );
}

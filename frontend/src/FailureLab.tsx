const failures = [
  ["stale evidence", "2200 ms > 1000 ms", "blocked"],
  ["occlusion", "target not visible", "blocked"],
  ["indirect injection", "untrusted visual instruction", "blocked"],
  ["contradiction", "open ≠ closed", "blocked"],
  ["distribution shift", "confidence 0.31", "abstained"],
];

export default function FailureLab() {
  return (
    <section className="failure-lab" aria-labelledby="failure-heading">
      <div className="failure-head">
        <div>
          <p className="eyebrow">ADVERSARIAL REPLAY · SEEDED FAILURES</p>
          <h2 id="failure-heading">Break the boundary, prove the safe response</h2>
        </div>
        <strong>5 / 5 contained</strong>
      </div>
      <div className="failure-grid">
        {failures.map(([kind, signal, outcome]) => (
          <article key={kind}>
            <small>{kind}</small>
            <span>{signal}</span>
            <strong>{outcome}</strong>
          </article>
        ))}
      </div>
      <footer>
        <span>protected violations</span>
        <strong>0</strong>
        <code>failure-injection.json</code>
      </footer>
    </section>
  );
}

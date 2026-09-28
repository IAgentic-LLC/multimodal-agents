const metrics = [
  ["Retrieval", "Recall@2", "0.50", "≥ 0.50"],
  ["Timing", "interval IoU", "0.667", "≥ 0.60"],
  ["Attribution", "citation precision", "1.00", "= 1.00"],
  ["Calibration", "Brier score", "0.070", "≤ 0.15"],
  ["Latency", "p95", "145 ms", "≤ 150 ms"],
  ["Safety", "violation rate", "0.00", "= 0.00"],
];

export default function EvaluationLab() {
  return (
    <section className="evaluation-lab" aria-labelledby="evaluation-heading">
      <div className="evaluation-head">
        <div>
          <p className="eyebrow">BOUNDARY EVALUATION · RELEASE REPORT</p>
          <h2 id="evaluation-heading">One passing average cannot hide one unsafe boundary</h2>
        </div>
        <strong>release passed</strong>
      </div>
      <div className="metric-grid">
        {metrics.map(([boundary, metric, value, threshold]) => (
          <article key={boundary}>
            <small>{boundary}</small>
            <b>{metric}</b>
            <strong>{value}</strong>
            <span>pass · {threshold}</span>
          </article>
        ))}
      </div>
      <footer>
        <span>6 / 6 explicit gates</span>
        <code>runs/gate-28/boundary-evaluation.json</code>
      </footer>
    </section>
  );
}

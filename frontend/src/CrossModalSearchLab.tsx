const directions = [
  {
    route: "TEXT → IMAGE",
    query: "checkout latency above threshold",
    result: "image:checkout-latency",
    score: "0.713428",
    latency: "16.10 ms",
  },
  {
    route: "SCREENSHOT → INCIDENT",
    query: "checkout dashboard pixels",
    result: "incident:checkout-latency",
    score: "0.718273",
    latency: "14.72 ms",
  },
  {
    route: "IMAGE → IMAGE",
    query: "checkout dashboard image",
    result: "image:checkout-latency",
    score: "1.000000",
    latency: "31.09 ms",
  },
];

export default function CrossModalSearchLab() {
  return (
    <section
      className="cross-modal-lab"
      aria-labelledby="cross-modal-heading"
    >
      <div className="cross-modal-head">
        <div>
          <p className="eyebrow">QDRANT · LIVE DIRECTIONAL EVALUATION</p>
          <h2 id="cross-modal-heading">One space, three different searches</h2>
        </div>
        <span>3 images · 3 incidents</span>
      </div>
      <div className="direction-grid">
        {directions.map((direction) => (
          <article key={direction.route}>
            <small>{direction.route}</small>
            <p>{direction.query}</p>
            <div className="route-arrow" aria-hidden="true">↓</div>
            <strong>{direction.result}</strong>
            <dl>
              <div><dt>score</dt><dd>{direction.score}</dd></div>
              <div><dt>latency</dt><dd>{direction.latency}</dd></div>
              <div><dt>top-1</dt><dd className="correct">correct</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <div className="cross-modal-footer">
        <span>tenant filter: tenant-blue</span>
        <span>model: gemini-embedding-2</span>
        <span>engine: qdrant-1.19.1</span>
      </div>
      <p className="scope-warning">
        Three controlled successes prove the path works. They do not estimate
        production accuracy.
      </p>
    </section>
  );
}

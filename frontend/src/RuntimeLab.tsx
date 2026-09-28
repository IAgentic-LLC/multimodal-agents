const spans = [
  ["queue.publish", "video · accepted"],
  ["queue.publish", "audio · accepted"],
  ["queue.publish", "sensor · rejected_full"],
  ["event.process", "event-1 · evidence retained"],
  ["event.process", "event-2 · evidence retained"],
];

export default function RuntimeLab() {
  return (
    <section className="runtime-lab" aria-labelledby="runtime-heading">
      <div className="runtime-head">
        <div>
          <p className="eyebrow">RUNTIME · OPEN TELEMETRY</p>
          <h2 id="runtime-heading">One trace explains pressure, work, and evidence</h2>
        </div>
        <span>trace ea90710a…f482</span>
      </div>
      <div className="runtime-body">
        <div className="span-tree">
          <div className="root-span"><b>session</b><span>tenant-blue</span></div>
          {spans.map(([name, detail], index) => (
            <article key={`${name}-${detail}`}>
              <small>SPAN {index + 1}</small>
              <b>{name}</b>
              <span>{detail}</span>
            </article>
          ))}
        </div>
        <div className="runtime-metrics">
          <div><small>QUEUE CAPACITY</small><strong>2</strong></div>
          <div><small>ACCEPTED</small><strong>2</strong></div>
          <div><small>REJECTED FULL</small><strong className="warn">1</strong></div>
          <div><small>PROCESS SAMPLES</small><strong>2</strong></div>
        </div>
      </div>
      <footer>IDs in telemetry · raw audio and image bytes excluded</footer>
    </section>
  );
}

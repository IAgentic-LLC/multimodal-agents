const events = [
  { time: "19:41:59", kind: "VOICE", value: "I will put these here." },
  { time: "19:42:03", kind: "VIDEO", value: "keys → kitchen counter" },
  { time: "19:44:00", kind: "HUMAN", value: "corrects → kitchen drawer" },
];

export default function EventMemoryLab() {
  return (
    <section className="memory-lab" aria-labelledby="memory-heading">
      <div className="memory-head">
        <div>
          <p className="eyebrow">APPEND-ONLY MULTIMODAL MEMORY</p>
          <h2 id="memory-heading">Corrections do not erase history</h2>
        </div>
        <span>entity: keys · 3 immutable events</span>
      </div>
      <div className="memory-flow">
        {events.map((event, index) => (
          <article key={event.kind}>
            <small>#{index + 1} · {event.time}</small>
            <b>{event.kind}</b>
            <p>{event.value}</p>
          </article>
        ))}
      </div>
      <div className="memory-projections">
        <p><small>KNOWN AT 19:43</small><strong>kitchen counter</strong></p>
        <span>correction arrives</span>
        <p><small>KNOWN AT 19:45</small><strong>kitchen drawer</strong></p>
      </div>
      <p className="memory-proof">
        original retained · correction links to evt-keys-video · digests intact
      </p>
    </section>
  );
}

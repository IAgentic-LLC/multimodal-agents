const events = [
  {
    label: "alarm tone",
    truth: "0.80–1.40 s",
    detected: "0.80–1.40 s",
    error: "0 ms",
    left: "26.67%",
    width: "20%",
  },
  {
    label: "knock",
    truth: "2.00–2.03 s",
    detected: "2.00–2.02 s",
    error: "−10 ms offset",
    left: "66.67%",
    width: "1%",
  },
];

export default function AcousticEventLab() {
  return (
    <section className="acoustic-lab" aria-labelledby="acoustic-heading">
      <div className="acoustic-head">
        <div>
          <p className="eyebrow">AUDIO BEYOND SPEECH · 20 MS FRAMES</p>
          <h2 id="acoustic-heading">A transcript cannot represent a knock</h2>
        </div>
        <span>16 kHz mono · RMS threshold 0.08</span>
      </div>
      <div className="audio-timeline" aria-label="Three-second audio timeline">
        <div className="timeline-rule">
          {events.map((event) => (
            <span
              className={`audio-event ${event.label.replace(" ", "-")}`}
              key={event.label}
              style={{ left: event.left, width: event.width }}
              title={event.label}
            />
          ))}
        </div>
        <div className="timeline-labels">
          <span>0 s</span><span>1 s</span><span>2 s</span><span>3 s</span>
        </div>
      </div>
      <div className="acoustic-events">
        {events.map((event) => (
          <article key={event.label}>
            <small>DETECTED EVENT</small>
            <h3>{event.label}</h3>
            <dl>
              <div><dt>ground truth</dt><dd>{event.truth}</dd></div>
              <div><dt>detector</dt><dd>{event.detected}</dd></div>
              <div><dt>boundary error</dt><dd>{event.error}</dd></div>
            </dl>
          </article>
        ))}
        <article className="acoustic-result">
          <small>RELEASE CHECK</small>
          <strong>2 / 2 events found</strong>
          <p>0 false positives · 0 missed events</p>
          <b>Audio events stay separate from speech transcripts.</b>
        </article>
      </div>
    </section>
  );
}

import { useState } from "react";

export default function ContradictionLab() {
  const [resolved, setResolved] = useState(false);
  return (
    <section className="conflict-lab" aria-labelledby="conflict-heading">
      <div className="conflict-head">
        <div>
          <p className="eyebrow">CONTRADICTION · EVIDENCE LIFECYCLE</p>
          <h2 id="conflict-heading">Disagreement is a record, not an overwrite</h2>
        </div>
        <span className={resolved ? "resolved" : "open"}>
          {resolved ? "resolved" : "open"}
        </span>
      </div>
      <div className="conflict-path">
        <article>
          <small>OBSERVATION A</small>
          <strong>camera-7 · closed</strong>
          <span>09:00:00.000 · reliability 0.72</span>
          <code>obs-camera-door</code>
        </article>
        <div className="conflict-node">
          <small>VALUE CONFLICT</small>
          <strong>door_state</strong>
          <span>same scope · 100 ms apart</span>
          <b>action withheld</b>
        </div>
        <article>
          <small>OBSERVATION B</small>
          <strong>reed-switch-2 · open</strong>
          <span>09:00:00.100 · reliability 0.99</span>
          <code>obs-reed-door</code>
        </article>
      </div>
      <div className="conflict-resolution">
        <div>
          <small>RESOLUTION EVIDENCE</small>
          <strong>{resolved ? "human-review-4 · open" : "not yet recorded"}</strong>
          <span>{resolved
            ? "physical latch inspected · originals retained"
            : "higher reliability alone cannot close the conflict"}</span>
        </div>
        <button onClick={() => setResolved(true)} disabled={resolved}>
          Record inspected latch
        </button>
      </div>
    </section>
  );
}

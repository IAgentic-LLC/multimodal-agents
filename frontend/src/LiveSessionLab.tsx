import { useMemo, useState } from "react";

import {
  frameForReference,
  latestFrameQueue,
  type TimedFrame,
} from "./liveSession";

const initialFrames: TimedFrame[] = [
  { id: "frame-0038", offsetMs: 3800 },
  { id: "frame-0047", offsetMs: 4700 },
];

export default function LiveSessionLab() {
  const [frames, setFrames] = useState(initialFrames);
  const [referenceOffset, setReferenceOffset] = useState(5000);
  const [dropped, setDropped] = useState(0);
  const capacity = 2;
  const maxAgeMs = 800;
  const decision = useMemo(
    () => frameForReference(frames, referenceOffset, maxAgeMs),
    [frames, referenceOffset],
  );

  const burst = () => {
    const incoming = [
      ...frames,
      { id: "frame-0048", offsetMs: 4800 },
      { id: "frame-0049", offsetMs: 4900 },
      { id: "frame-0050", offsetMs: 5000 },
    ];
    const kept = latestFrameQueue(incoming, capacity);
    setDropped((value) => value + incoming.length - kept.length);
    setFrames(kept);
    setReferenceOffset(5100);
  };

  return (
    <section className="session-lab" aria-labelledby="session-lab-heading">
      <div>
        <p className="eyebrow">LIVE SESSION POLICY</p>
        <h2 id="session-lab-heading">Bind speech to a fresh frame</h2>
        <p>
          Keep the newest frames under pressure. Refuse a visual reference
          when its latest eligible frame is older than 800 milliseconds.
        </p>
      </div>
      <div className="session-strip" aria-label="Buffered video frames">
        {frames.map((frame) => (
          <span key={frame.id}>
            <strong>{frame.id}</strong>{frame.offsetMs} ms
          </span>
        ))}
      </div>
      <dl className="session-metrics">
        <div><dt>Reference</dt><dd>{referenceOffset} ms</dd></div>
        <div><dt>Decision</dt><dd>{decision.status}</dd></div>
        <div><dt>Frame age</dt><dd>{decision.ageMs ?? "none"} ms</dd></div>
        <div><dt>Dropped</dt><dd>{dropped}</dd></div>
      </dl>
      <div className="session-actions">
        <button className="quiet" onClick={burst}>Simulate frame burst</button>
        <button
          className="quiet"
          onClick={() => setReferenceOffset(6200)}
        >
          Advance until stale
        </button>
        <button
          className="quiet"
          onClick={() => {
            setFrames(initialFrames);
            setReferenceOffset(5000);
            setDropped(0);
          }}
        >
          Reset session
        </button>
      </div>
    </section>
  );
}

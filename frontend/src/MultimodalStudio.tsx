import { type KeyboardEvent, useId, useState } from "react";

type View = "timeline" | "evidence" | "search" | "evaluation" | "replay";

const views: { id: View; label: string }[] = [
  { id: "timeline", label: "Timeline" },
  { id: "evidence", label: "Evidence" },
  { id: "search", label: "Search" },
  { id: "evaluation", label: "Evaluation" },
  { id: "replay", label: "Replay" },
];

const timeline = [
  ["00:00.000", "video", "frame-0087", "retained"],
  ["00:00.140", "voice", "“Put these here”", "retained"],
  ["00:00.420", "fusion", "keys → kitchen counter", "supported"],
  ["00:00.610", "memory", "event mem-104 written", "verified"],
];

export default function MultimodalStudio() {
  const [view, setView] = useState<View>("timeline");
  const prefix = useId();
  const select = (next: View) => setView(next);
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!(["ArrowLeft", "ArrowRight", "Home", "End"]
      .includes(event.key))) return;
    event.preventDefault();
    const target = event.key === "Home" ? 0
      : event.key === "End" ? views.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1)
          + views.length) % views.length;
    select(views[target].id);
    document.getElementById(`${prefix}-tab-${views[target].id}`)?.focus();
  };

  return (
    <section className="studio" aria-labelledby={`${prefix}-title`}>
      <header className="studio-header">
        <div>
          <p className="eyebrow">IAGENTIC MULTIMODAL STUDIO</p>
          <h2 id={`${prefix}-title`}>Inspect one session end to end</h2>
        </div>
        <div className="studio-health" aria-label="Session health">
          <span /> LIVE TRACE <strong>5 / 5 gates</strong>
        </div>
      </header>

      <div className="studio-context">
        <label>
          Session
          <select defaultValue="session-kitchen-104">
            <option value="session-kitchen-104">session-kitchen-104</option>
          </select>
        </label>
        <dl>
          <div><dt>Tenant</dt><dd>tenant-blue</dd></div>
          <div><dt>Trace</dt><dd>ea90710a…f482</dd></div>
          <div><dt>Outcome</dt><dd>supported</dd></div>
        </dl>
      </div>

      <div className="studio-tabs" role="tablist" aria-label="Session tools">
        {views.map((item, index) => (
          <button
            id={`${prefix}-tab-${item.id}`}
            key={item.id}
            role="tab"
            aria-selected={view === item.id}
            aria-controls={`${prefix}-panel-${item.id}`}
            tabIndex={view === item.id ? 0 : -1}
            onClick={() => select(item.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        className="studio-panel"
        id={`${prefix}-panel-${view}`}
        role="tabpanel"
        aria-labelledby={`${prefix}-tab-${view}`}
        tabIndex={0}
      >
        {view === "timeline" && (
          <div className="studio-timeline">
            {timeline.map(([time, modality, detail, state]) => (
              <article key={time}>
                <time>{time}</time><b>{modality}</b><span>{detail}</span>
                <em>{state}</em>
              </article>
            ))}
          </div>
        )}
        {view === "evidence" && (
          <div className="studio-evidence-grid">
            <article><small>VIDEO REGION</small><b>frame-0087</b>
              <span>sha256: 51a7…29cc</span><em>retained</em></article>
            <article><small>VOICE INTERVAL</small><b>140–390 ms</b>
              <span>“Put these here”</span><em>retained</em></article>
            <article><small>WORLD STATE</small><b>keys</b>
              <span>kitchen counter · 0.94</span><em>supported</em></article>
          </div>
        )}
        {view === "search" && (
          <div className="studio-result"><small>QUERY</small>
            <b>Where did I put my keys?</b><span>1 temporal result</span>
            <p>Kitchen counter at 19:42 · video + voice evidence</p></div>
        )}
        {view === "evaluation" && (
          <div className="studio-score-grid">
            {[["retrieval", "1.00"], ["attribution", "1.00"],
              ["safety", "PASS"], ["latency p95", "84 ms"]]
              .map(([name, value]) => <article key={name}>
                <small>{name}</small><strong>{value}</strong></article>)}
          </div>
        )}
        {view === "replay" && (
          <div className="studio-result"><small>DETERMINISTIC REPLAY</small>
            <b>digest 9da6…b142</b><span>4 events · same order</span>
            <p>Hazard supported · contradiction clear · action verified</p>
            <button type="button">Replay retained fixture</button></div>
        )}
      </div>
    </section>
  );
}

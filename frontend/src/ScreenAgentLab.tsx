import { useState } from "react";

type Outcome = "pending" | "proved" | "refused";

export default function ScreenAgentLab() {
  const [outcome, setOutcome] = useState<Outcome>("pending");
  const success = outcome === "proved";
  const refused = outcome === "refused";
  const events = outcome === "proved"
    ? ["requested", "approved", "executed", "postcondition.proved"]
    : outcome === "refused"
      ? ["requested", "action.refused: stale revision"]
      : ["requested", "awaiting scenario"];

  return (
    <section className="agent-lab" aria-labelledby="agent-heading">
      <div className="agent-summary">
        <p className="eyebrow">SAFE SCREEN AGENT</p>
        <h2 id="agent-heading">One task, two release tests</h2>
        <p>
          The same narrow deploy tool either proves a local result or refuses
          stale evidence before a side effect.
        </p>
        <div className="agent-controls">
          <button className="save" onClick={() => setOutcome("proved")}>
            Run approved current action
          </button>
          <button className="quiet" onClick={() => setOutcome("refused")}>
            Plant stale target
          </button>
          <button className="quiet" onClick={() => setOutcome("pending")}>
            Reset trace
          </button>
        </div>
      </div>
      <div className="agent-verdict">
        <span className={success ? "good" : refused ? "bad" : "neutral"}>
          {outcome}
        </span>
        <dl>
          <div><dt>Permission</dt><dd>release.deploy</dd></div>
          <div><dt>Approval</dt><dd>approval-7</dd></div>
          <div><dt>Sandbox</dt><dd>local release-42</dd></div>
          <div><dt>Result</dt><dd>{success ? "release-43 deployed" : refused
            ? "no state change" : "not executed"}</dd></div>
        </dl>
      </div>
      <ol className="agent-trace" aria-label="Retained action trace">
        {events.map((event) => <li key={event}>{event}</li>)}
      </ol>
    </section>
  );
}

import { useState } from "react";

type Phase = "stale" | "ready" | "proved";

export default function SafeActionLab() {
  const [phase, setPhase] = useState<Phase>("stale");
  const detail = phase === "stale"
    ? "Rejected: observed rev-41, current rev-42"
    : phase === "ready"
      ? "Allowed: identity, revision, geometry, and hit target agree"
      : "Proved: release-43 reports deployed";

  return (
    <section className="action-lab" aria-labelledby="action-heading">
      <div className="action-head">
        <div>
          <p className="eyebrow">REVISION-BOUND ACTION</p>
          <h2 id="action-heading">Reject, refresh, act, prove</h2>
        </div>
        <span className={`action-phase ${phase}`}>{phase}</span>
      </div>
      <div className="action-flow" aria-label="Safe action sequence">
        <span className="done">Identify<br /><small>deploy-build</small></span>
        <b>→</b>
        <span className={phase === "stale" ? "failed" : "done"}>
          Preconditions<br /><small>revision + geometry</small>
        </span>
        <b>→</b>
        <span className={phase === "proved" ? "done" : "waiting"}>
          Execute<br /><small>scoped click</small>
        </span>
        <b>→</b>
        <span className={phase === "proved" ? "done" : "waiting"}>
          Verify<br /><small>release-43</small>
        </span>
      </div>
      <div className="action-footer">
        <p>{detail}</p>
        {phase === "stale" && (
          <button className="quiet" onClick={() => setPhase("ready")}>
            Refresh evidence
          </button>
        )}
        {phase === "ready" && (
          <button className="save" onClick={() => setPhase("proved")}>
            Execute and verify
          </button>
        )}
        {phase === "proved" && (
          <button className="quiet" onClick={() => setPhase("stale")}>
            Reset scenario
          </button>
        )}
      </div>
    </section>
  );
}

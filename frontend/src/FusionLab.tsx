import { useState } from "react";

type Signal = {
  source: string;
  value: "actionable" | "blocked";
  revision: string;
};

const baseSignals: Signal[] = [
  { source: "Pixels", value: "blocked", revision: "frame-184" },
  { source: "DOM", value: "actionable", revision: "dom-912" },
  { source: "Accessibility", value: "actionable", revision: "ax-912" },
  { source: "Release API", value: "blocked", revision: "release-42" },
];

export default function FusionLab() {
  const [reconciled, setReconciled] = useState(false);
  const signals = reconciled
    ? baseSignals.map((item) => ({ ...item, value: "actionable" as const }))
    : baseSignals;
  const values = new Set(signals.map((item) => item.value));
  const status = values.size === 1 ? "agreed" : "conflicted";

  return (
    <section className="fusion-lab" aria-labelledby="fusion-heading">
      <div className="fusion-head">
        <div>
          <p className="eyebrow">SOURCE-PRESERVING FUSION</p>
          <h2 id="fusion-heading">Agreement is earned, not overwritten</h2>
        </div>
        <span className={`fusion-status ${status}`}>{status}</span>
      </div>
      <div className="signal-grid">
        {signals.map((signal) => (
          <article key={signal.source}>
            <p>{signal.source}</p>
            <strong>{signal.value}</strong>
            <small>{signal.revision}</small>
          </article>
        ))}
      </div>
      <div className="fusion-footer">
        <p>
          {status === "conflicted"
            ? "Action withheld. Four observations remain inspectable."
            : "Precondition satisfied. Action may proceed."}
        </p>
        <button
          className="quiet"
          onClick={() => setReconciled((value) => !value)}
        >
          {reconciled ? "Restore conflict" : "Observe reconciled state"}
        </button>
      </div>
    </section>
  );
}

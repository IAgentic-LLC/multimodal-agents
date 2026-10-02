import { useState } from "react";

type Specialist = { role: string; status: "completed" | "failed"; claim?: string; evidence_ids?: string[]; latency_ms?: number; detail?: string };
type Orchestration = { trace_id: string; authority: string; status: "completed" | "partial_failure"; duration_ms: number; specialists: Specialist[]; evidence_backed_claims: number; action_gate: string };

export default function MultiAgentLab() {
  const [question, setQuestion] = useState("Is the loading-bay door closed?");
  const [result, setResult] = useState<Orchestration | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setWorking(true); setError("");
    try {
      const response = await fetch("/api/orchestrations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
      if (!response.ok) throw new Error(`Coordinator returned ${response.status}`);
      setResult(await response.json() as Orchestration);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Orchestration failed"); }
    finally { setWorking(false); }
  };
  return (
    <section className="runtime-lab" aria-labelledby="multi-agent-heading">
      <div className="runtime-head"><div><p className="eyebrow">LIVE A2A ORCHESTRATION</p><h2 id="multi-agent-heading">Delegate capabilities, not trust</h2></div><span data-testid="orchestration-state">{working ? "DELEGATING" : result?.status.toUpperCase() ?? "READY"}</span></div>
      <div className="orchestration-controls"><label htmlFor="orchestration-question">Question for the specialists</label><div><input id="orchestration-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={240} /><button type="button" onClick={run} disabled={working || question.length < 3}>{working ? "Running…" : "Run live orchestration"}</button></div></div>
      {error && <p className="orchestration-error" role="alert">{error}</p>}
      <div className="runtime-body" aria-live="polite">
        <div className="span-tree"><div className="root-span"><b>FastAPI coordinator</b><span>{result?.trace_id ?? "waiting for a trace"}</span></div>
          {(result?.specialists ?? []).map((agent) => <article key={agent.role} data-status={agent.status}><small>{agent.status.toUpperCase()}</small><b>{agent.role} specialist</b><span>{agent.claim ?? agent.detail}</span><code>{agent.evidence_ids?.join(", ") ?? "no evidence"}</code><em>{agent.latency_ms == null ? "" : `${agent.latency_ms} ms`}</em></article>)}
          {!result && <p className="orchestration-empty">Run the coordinator to create a real, shared trace.</p>}
        </div>
        <div className="runtime-metrics"><div><small>DELEGATED</small><strong>{result?.specialists.length ?? 0}</strong></div><div><small>EVIDENCE CLAIMS</small><strong>{result?.evidence_backed_claims ?? 0}</strong></div><div><small>END-TO-END</small><strong>{result ? `${result.duration_ms} ms` : "—"}</strong></div><div><small>ACTION GATE</small><strong>BLOCKED</strong></div></div>
      </div>
      <footer>Auth0 M2M · A2A 1.0 · shared trace · evidence IDs · observe-only authority</footer>
    </section>
  );
}

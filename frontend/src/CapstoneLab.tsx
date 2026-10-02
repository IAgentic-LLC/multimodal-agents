import { useState } from "react";

type Specialist = {
  role: string;
  status: string;
  claim?: string;
  evidence_ids?: string[];
  chapter?: number;
  latency_ms?: number;
  detail?: string;
};

type Orchestration = {
  trace_id: string;
  status: string;
  duration_ms: number;
  specialists: Specialist[];
  evidence_backed_claims: number;
};

type Decision = "approved" | "rejected";

const EXAMPLE_QUESTIONS = [
  "How many tracked objects kept their identity across the video?",
  "Show the real nuclear lineage graph with arrows.",
  "Widen the high-intensity region threshold in the MRI segmentation.",
];

function specialistByRole(result: Orchestration | null, role: string): Specialist | undefined {
  return result?.specialists.find((item) => item.role === role);
}

function firstEvidenceId(specialist: Specialist | undefined): string | undefined {
  return specialist?.evidence_ids?.[0];
}

function displayStatus(specialist: Specialist | undefined): string {
  if (!specialist) return "idle";
  const hasEvidence = (specialist.evidence_ids?.length ?? 0) > 0;
  if (specialist.status === "completed" && !hasEvidence) return "no_evidence";
  return specialist.status;
}

export default function CapstoneLab() {
  const [question, setQuestion] = useState(EXAMPLE_QUESTIONS[0]);
  const [result, setResult] = useState<Orchestration | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);

  const run = async () => {
    setWorking(true);
    setError("");
    setDecision(null);
    try {
      const response = await fetch("/api/orchestrations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!response.ok) throw new Error(`Coordinator returned ${response.status}`);
      setResult((await response.json()) as Orchestration);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Orchestration failed");
    } finally {
      setWorking(false);
    }
  };

  const analysis = specialistByRole(result, "analysis");
  const visualization = specialistByRole(result, "visualization");
  const editProposal = specialistByRole(result, "edit-proposal");
  const canDecide = editProposal?.status === "proposed_pending_approval" && !decision;

  const recordDecision = async (next: Decision) => {
    if (!editProposal) return;
    setDecisionBusy(true);
    try {
      const response = await fetch("/api/edit-proposals/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          claim: editProposal.claim ?? "",
          evidence_ids: editProposal.evidence_ids ?? [],
          chapter: editProposal.chapter ?? null,
          decision: next,
          reviewer: "reader",
        }),
      });
      if (!response.ok) throw new Error(`Decision log returned ${response.status}`);
      setDecision(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not record the decision");
    } finally {
      setDecisionBusy(false);
    }
  };

  return (
    <section className="capstone-lab" aria-labelledby="capstone-heading">
      <div className="capstone-head">
        <div>
          <p className="eyebrow">CAPSTONE: ANALYSIS, VISUALIZATION, AND EDITING</p>
          <h2 id="capstone-heading">One question, three grounded answers</h2>
        </div>
        <span className="status-pill" data-testid="capstone-state">
          {working ? "ASKING" : result?.status.toUpperCase() ?? "READY"}
        </span>
      </div>

      <div className="capstone-controls">
        <label htmlFor="capstone-question">Question for the specialists</label>
        <div>
          <input
            id="capstone-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={240}
            list="capstone-examples"
          />
          <datalist id="capstone-examples">
            {EXAMPLE_QUESTIONS.map((example) => (
              <option key={example} value={example} />
            ))}
          </datalist>
          <button type="button" onClick={run} disabled={working || question.length < 3}>
            {working ? "Asking…" : "Ask the specialists"}
          </button>
        </div>
      </div>

      {error && (
        <p className="capstone-error" role="alert">
          {error}
        </p>
      )}

      <div className="capstone-grid" aria-live="polite">
        <article className="capstone-card" data-role="analysis">
          <header>
            <p className="eyebrow">ANALYSIS</p>
            <span className="capstone-pill" data-state={displayStatus(analysis)}>
              {analysis ? displayStatus(analysis).replace(/_/g, " ") : "waiting"}
            </span>
          </header>
          <p className="capstone-claim">
            {analysis?.claim ?? "Ask a question to see a cited answer, or an honest refusal."}
          </p>
          {firstEvidenceId(analysis) && <code>{firstEvidenceId(analysis)}</code>}
        </article>

        <article className="capstone-card" data-role="visualization">
          <header>
            <p className="eyebrow">VISUALIZATION</p>
            <span className="capstone-pill" data-state={displayStatus(visualization)}>
              {visualization ? displayStatus(visualization).replace(/_/g, " ") : "waiting"}
            </span>
          </header>
          {visualization?.evidence_ids?.[0] ? (
            <figure className="capstone-figure">
              <img
                src={`/api/evidence-image?source_file=${encodeURIComponent(visualization.evidence_ids[0])}`}
                alt={`Retained figure for chapter ${visualization.chapter ?? "?"}, cited as the best match for this question.`}
              />
              <figcaption>{visualization.evidence_ids[0]}</figcaption>
            </figure>
          ) : (
            <p className="capstone-claim">
              {visualization?.claim ?? "A matching retained figure will render here when one is found."}
            </p>
          )}
        </article>

        <article className="capstone-card" data-role="edit-proposal">
          <header>
            <p className="eyebrow">EDIT PROPOSAL</p>
            <span
              className="capstone-pill"
              data-state={decision ?? (editProposal ? editProposal.status : "idle")}
            >
              {decision ?? (editProposal ? editProposal.status.replace(/_/g, " ") : "waiting")}
            </span>
          </header>
          <p className="capstone-claim">
            {editProposal?.claim ?? "A proposed, bounded edit will appear here. It is never applied automatically."}
          </p>
          {firstEvidenceId(editProposal) && <code>{firstEvidenceId(editProposal)}</code>}
          {canDecide && (
            <div className="capstone-decision">
              <button type="button" onClick={() => recordDecision("approved")} disabled={decisionBusy}>
                Approve
              </button>
              <button type="button" className="quiet" onClick={() => recordDecision("rejected")} disabled={decisionBusy}>
                Reject
              </button>
            </div>
          )}
          {decision && (
            <p className="capstone-decision-note">
              Logged as {decision}. This only records a decision; it never edits the retained evidence file itself.
            </p>
          )}
        </article>
      </div>

      <footer>
        {result ? `trace ${result.trace_id} · ${result.evidence_backed_claims} evidence-backed claims · ${result.duration_ms} ms` : "Hybrid search over the book's own retained evidence · gemini-embedding-2 · OpenSearch"}
      </footer>
    </section>
  );
}

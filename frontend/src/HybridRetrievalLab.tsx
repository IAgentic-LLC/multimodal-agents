const cases = [
  {
    label: "EXACT IDENTIFIER",
    query: "INC-4827",
    dense: "wrong: INC-4828",
    sparse: "correct: INC-4827",
    fused: "rank 1: INC-4827",
    decision: "supported",
    latency: "28.95 ms + 1,814 ms",
  },
  {
    label: "SEMANTIC PARAPHRASE",
    query: "proof of purchase appears too slowly after paying",
    dense: "correct receipt incident",
    sparse: "wrong authorization incident",
    fused: "tie: two incidents",
    decision: "reranked to evidence",
    latency: "33.37 ms + 3,515 ms",
  },
  {
    label: "UNSUPPORTED QUESTION",
    query: "Which database password was leaked?",
    dense: "plausible false leads",
    sparse: "no candidates",
    fused: "dense candidates only",
    decision: "abstain",
    latency: "24.95 ms + 1,572 ms",
  },
];

export default function HybridRetrievalLab() {
  return (
    <section className="hybrid-lab" aria-labelledby="hybrid-heading">
      <div className="hybrid-head">
        <div>
          <p className="eyebrow">QDRANT · DENSE + SPARSE + RERANK</p>
          <h2 id="hybrid-heading">Each retrieval leg fails differently</h2>
        </div>
        <span>6 documents · 3 labeled queries</span>
      </div>
      <div className="hybrid-cases">
        {cases.map((item) => (
          <article key={item.label}>
            <small>{item.label}</small>
            <h3>{item.query}</h3>
            <div className="retrieval-path">
              <p><b>Dense</b><span>{item.dense}</span></p>
              <p><b>Sparse</b><span>{item.sparse}</span></p>
              <p><b>RRF</b><span>{item.fused}</span></p>
            </div>
            <footer>
              <strong>{item.decision}</strong>
              <span>{item.latency}</span>
            </footer>
          </article>
        ))}
      </div>
      <div className="hybrid-provenance">
        <span>dense: gemini-embedding-2</span>
        <span>sparse: client BM25</span>
        <span>fusion: Qdrant RRF</span>
        <span>reranker: gemini-3.8-flash</span>
      </div>
    </section>
  );
}

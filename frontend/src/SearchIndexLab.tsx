const results = [
  { rank: 1, kind: "text", id: "paragraph:1", score: 0.699244, answer: false },
  { rank: 2, kind: "table", id: "table:1", score: 0.682303, answer: true },
  { rank: 3, kind: "image", id: "figure:1", score: 0.632736, answer: true },
];

export default function SearchIndexLab() {
  return (
    <section className="search-lab" aria-labelledby="search-heading">
      <div className="search-head">
        <div>
          <p className="eyebrow">MULTIMODAL INDEX · LIVE EMBEDDINGS</p>
          <h2 id="search-heading">A vector hit is not yet evidence</h2>
        </div>
        <span>768 dimensions · 2,053 ms</span>
      </div>
      <div className="query-box">
        <small>QUERY</small>
        <strong>Which service exceeds the threshold?</strong>
      </div>
      <ol className="search-results">
        {results.map((result) => (
          <li key={result.id} className={result.answer ? "answer" : "lead"}>
            <b>{result.rank}</b>
            <span className="modality">{result.kind}</span>
            <code>report:p1:{result.id}</code>
            <span>{result.score.toFixed(6)}</span>
            <em>{result.answer ? "contains evidence" : "context only"}</em>
          </li>
        ))}
      </ol>
      <div className="index-provenance">
        <span>index: release-report-v1</span>
        <span>parser: apache-tika-4.0.0</span>
        <span>model: gemini-embedding-2</span>
      </div>
      <p className="search-warning">
        Rank 1 names the topic but not the service. Retrieval must preserve
        object type and provenance so a reranker can prefer answer-bearing evidence.
      </p>
    </section>
  );
}

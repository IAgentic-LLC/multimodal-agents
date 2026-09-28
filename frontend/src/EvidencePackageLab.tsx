const variants = [
  {
    name: "COMPLETE",
    modalities: "text + table + image",
    citation: "table row",
    latency: "4,936 ms",
  },
  {
    name: "WITHOUT TEXT",
    modalities: "table + image",
    citation: "table row",
    latency: "3,057 ms",
  },
  {
    name: "WITHOUT TABLE",
    modalities: "text + image",
    citation: "paragraph",
    latency: "2,318 ms",
  },
  {
    name: "WITHOUT IMAGE",
    modalities: "text + table",
    citation: "table row",
    latency: "1,788 ms",
  },
];

export default function EvidencePackageLab() {
  return (
    <section className="package-lab" aria-labelledby="package-heading">
      <div className="package-head">
        <div>
          <p className="eyebrow">MULTIMODAL RAG · REMOVAL TEST</p>
          <h2 id="package-heading">The answer survives one missing modality</h2>
        </div>
        <span>4 provider calls · 0 citation errors</span>
      </div>
      <div className="package-question">
        <small>QUESTION</small>
        <strong>Which service requires investigation?</strong>
        <b>Search API</b>
      </div>
      <div className="package-variants">
        {variants.map((variant) => (
          <article key={variant.name}>
            <small>{variant.name}</small>
            <strong>{variant.modalities}</strong>
            <dl>
              <div><dt>citation</dt><dd>{variant.citation}</dd></div>
              <div><dt>verified</dt><dd className="correct">yes</dd></div>
              <div><dt>latency</dt><dd>{variant.latency}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <div className="citation-strip">
        <code>document-layout.docx#table=1&amp;row=search-api</code>
        <span>“Search API | 3.4% | Investigate”</span>
      </div>
    </section>
  );
}

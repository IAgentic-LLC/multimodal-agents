const rows = [
  ["Service", "Error rate", "Decision"],
  ["Vision API", "0.8%", "pass"],
  ["Search API", "3.4%", "investigate"],
];

export default function DocumentLayoutLab() {
  return (
    <section className="document-lab" aria-labelledby="document-heading">
      <div className="document-head">
        <div>
          <p className="eyebrow">LAYOUT-PRESERVING DOCUMENT</p>
          <h2 id="document-heading">A page is more than its text</h2>
        </div>
        <span>DOCX · Tika 4.0.0</span>
      </div>
      <div className="document-page">
        <h3>Release Readiness Report</h3>
        <p>The decision depends on the metrics and the related figure.</p>
        <table>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row[0]}>
                {row.map((cell) => index === 0
                  ? <th key={cell}>{cell}</th>
                  : <td key={cell}>{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        <figure>
          <div className="mini-chart" aria-label="Error-rate chart">
            <span style={{ height: "24%" }}>0.8%</span>
            <span style={{ height: "84%" }}>3.4%</span>
          </div>
          <figcaption>
            Figure 1 · Search API exceeds the review threshold.
          </figcaption>
        </figure>
      </div>
      <div className="document-evidence">
        <article><strong>1</strong><span>heading</span></article>
        <article><strong>1</strong><span>table · 3 rows</span></article>
        <article><strong>1</strong><span>embedded figure</span></article>
        <article><strong>1</strong><span>caption_of relation</span></article>
      </div>
      <p className="document-warning">
        Flat text retains the words but loses the typed table, embedded asset,
        and explicit caption relationship.
      </p>
    </section>
  );
}

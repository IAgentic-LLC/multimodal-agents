const facts = [
  ["FRAME", "717 ms", "1280 x 720 JPEG · 16,535 B"],
  ["VOICE", "717–2,027 ms", "Opus audio · 20,511 B"],
  ["RECORD", "same session clock", "JSONL metadata · 582 B"],
];

export default function OpeningEvidenceLabs() {
  return (
    <>
      <section className="opening-lab" aria-label="Bind this to one session clock">
        <header><div><p className="eyebrow">GATE 1 · RETAINED RUN</p>
          <h2>Bind “this” to one session clock</h2></div>
          <strong>CAPTURED</strong></header>
        <div className="opening-grid">
          {facts.map(([kind, time, detail]) => <article key={kind}>
            <small>{kind}</small><b>{time}</b><span>{detail}</span>
          </article>)}
        </div>
        <footer><span>Initial failure: empty audio</span>
          <b>Fix: audio-only recorder + 250 ms chunks</b></footer>
      </section>

      <section className="opening-lab" aria-label="An evidence event can be inspected">
        <header><div><p className="eyebrow">EVIDENCE EVENT</p>
          <h2>An answer is not evidence</h2></div><strong>TRACEABLE</strong></header>
        <div className="evidence-flow">
          <article><small>OBSERVATION</small><b>red mug</b>
            <span>frame-0007 · region [0.42, 0.31, 0.68, 0.79]</span></article>
          <i>+</i><article><small>REFERENCE</small><b>“this”</b>
            <span>voice 717–2,027 ms · session clock</span></article>
          <i>→</i><article><small>SUPPORTED CLAIM</small><b>this = red mug</b>
            <span>source IDs, time, region, transformation</span></article>
        </div>
        <footer><span>claim</span><span>evidence</span><span>provenance</span>
          <b>inspectable together</b></footer>
      </section>

      <section className="opening-lab" aria-label="Keep each modality honest">
        <header><div><p className="eyebrow">GATE 2 · LIVE GEMINI RUN</p>
          <h2>One scene, two stories</h2></div><strong>MEASURED</strong></header>
        <div className="story-grid">
          <article className="unsafe"><small>JOINT INPUT · 11,665 ms</small>
            <b>“inverted text”</b><span>confidence 0.95</span>
            <em>Visible words changed what the model said it heard.</em></article>
          <article className="protected"><small>SPLIT INPUT · 6,644 + 2,106 ms</small>
            <b>“in the bad check for”</b><span>image check: UNRESOLVED</span>
            <em>Audio stays audio; vision may support, not rewrite it.</em></article>
        </div>
      </section>

      <section className="opening-lab" aria-label="Build a world state without erasing evidence">
        <header><div><p className="eyebrow">APPEND-ONLY WORLD STATE</p>
          <h2>State is a projection over events</h2></div><strong>REVISION 2</strong></header>
        <div className="world-flow">
          <article><small>EVENT 1 · observed</small><b>keys → counter</b>
            <span>camera frame + spoken reference</span></article>
          <i>→</i><article><small>EVENT 2 · corrected</small><b>keys → drawer</b>
            <span>later observation; Event 1 retained</span></article>
          <i>→</i><article><small>CURRENT PROJECTION</small><b>drawer</b>
            <span>supported by Event 2 · history intact</span></article>
        </div>
        <footer><span>Where are the keys now?</span><b>drawer · cite Event 2</b></footer>
      </section>
    </>
  );
}

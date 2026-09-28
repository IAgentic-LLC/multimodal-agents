const answers = [
  {
    question: "Where were the keys, as known at 19:43?",
    answer: "kitchen counter",
    evidence: "video · kitchen.mp4#t=4,6",
  },
  {
    question: "Where were the keys, as known at 19:45?",
    answer: "kitchen drawer",
    evidence: "correction · review:1",
  },
  {
    question: "What changed?",
    answer: "counter → drawer at 19:44",
    evidence: "video + correction",
  },
];

export default function MemoryQueryLab() {
  return (
    <section className="memory-query-lab" aria-labelledby="memory-query-heading">
      <div className="memory-query-head">
        <div>
          <p className="eyebrow">TEMPORAL MEMORY · EVIDENCE QUERIES</p>
          <h2 id="memory-query-heading">Ask what was known, not only what is true now</h2>
        </div>
        <span>voice → video → correction</span>
      </div>
      <div className="memory-query-grid">
        {answers.map((item) => (
          <article key={item.question}>
            <small>QUESTION</small>
            <h3>{item.question}</h3>
            <strong>{item.answer}</strong>
            <p>{item.evidence}</p>
          </article>
        ))}
      </div>
      <div className="time-axes">
        <span>world time: observation applies at 19:42</span>
        <span>record time: correction becomes known at 19:44</span>
      </div>
    </section>
  );
}

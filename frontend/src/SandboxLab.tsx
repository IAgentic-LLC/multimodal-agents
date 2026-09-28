const events = [
  ["0 ms", "video", "door closed"],
  ["100 ms", "sensor", "door open"],
  ["500 ms", "sensor", "68 Cel"],
  ["1200 ms", "audio", "alarm"],
  ["1400 ms", "voice", "Lock the door"],
];

export default function SandboxLab() {
  return (
    <section className="sandbox-lab" aria-labelledby="sandbox-heading">
      <div className="sandbox-head">
        <div>
          <p className="eyebrow">MULTIMODAL SANDBOX · SEED 24028</p>
          <h2 id="sandbox-heading">Replay the same world, score every boundary</h2>
        </div>
        <span>digest 9c6f2730…df583</span>
      </div>
      <div className="sandbox-timeline">
        {events.map(([time, modality, value]) => (
          <article key={`${time}-${modality}`}>
            <small>{time}</small>
            <b>{modality}</b>
            <span>{value}</span>
          </article>
        ))}
      </div>
      <div className="sandbox-score">
        <div><small>HAZARD</small><strong>pass</strong><span>supported</span></div>
        <div><small>DOOR STATE</small><strong>pass</strong><span>conflicted</span></div>
        <div><small>ACTION</small><strong>pass</strong><span>denied</span></div>
        <div><small>REPLAY</small><strong>identical</strong><span>3 / 3 checks</span></div>
      </div>
    </section>
  );
}

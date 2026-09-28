const observations = [
  { source: "camera-7", property: "door", value: "closed", score: "0.72" },
  { source: "reed-switch-2", property: "door", value: "open", score: "0.99" },
  { source: "thermocouple-4", property: "temperature", value: "68 Cel", score: "0.97" },
  { source: "microphone-3", property: "audio event", value: "alarm", score: "0.88" },
];

export default function SensorWorldLab() {
  return (
    <section className="sensor-lab" aria-labelledby="sensor-heading">
      <div className="sensor-head">
        <div>
          <p className="eyebrow">SENSORS · SOURCE-PRESERVING WORLD STATE</p>
          <h2 id="sensor-heading">Fuse evidence without making it agree</h2>
        </div>
        <span>phenomenon time + result time</span>
      </div>
      <div className="sensor-grid">
        {observations.map((item) => (
          <article key={item.source}>
            <small>{item.source}</small>
            <b>{item.property}</b>
            <strong>{item.value}</strong>
            <span>quality good · reliability {item.score}</span>
          </article>
        ))}
      </div>
      <div className="world-state">
        <div>
          <small>DOOR STATE</small>
          <strong className="conflicted">conflicted</strong>
          <span>camera says closed · switch says open</span>
        </div>
        <div>
          <small>DERIVED HAZARD</small>
          <strong className="supported">supported</strong>
          <span>68 Cel + alarm within 0.7 s</span>
        </div>
        <div>
          <small>EVIDENCE</small>
          <strong>2 source IDs</strong>
          <span>temperature + acoustic event</span>
        </div>
      </div>
    </section>
  );
}

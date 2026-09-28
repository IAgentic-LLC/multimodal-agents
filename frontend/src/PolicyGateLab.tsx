const decisions = [
  ["No approval", "pending", "parameter-bound approval required"],
  ["Exact approval", "allowed", "approval-88 · $45 · order-A1002"],
  ["Amount changed", "denied", "approval scope mismatch · $450"],
  ["Open conflict", "denied", "conflict-door-0001"],
];

export default function PolicyGateLab() {
  return (
    <section className="policy-lab" aria-labelledby="policy-heading">
      <div className="policy-head">
        <div>
          <p className="eyebrow">EVIDENCE BEFORE ACTION · POLICY V1</p>
          <h2 id="policy-heading">Approval binds the action, not the conversation</h2>
        </div>
        <span>actor · tool · target · parameters</span>
      </div>
      <div className="policy-decisions">
        {decisions.map(([name, outcome, reason]) => (
          <article key={name}>
            <small>{name}</small>
            <strong className={outcome}>{outcome}</strong>
            <span>{reason}</span>
          </article>
        ))}
      </div>
      <footer>
        <code>obs-order + obs-identity</code>
        <b>policy version and decision evidence retained</b>
      </footer>
    </section>
  );
}

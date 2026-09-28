import { useRef, useState } from "react";

export default function ScreenStateLab() {
  const actionRef = useRef<HTMLButtonElement>(null);
  const [blocked, setBlocked] = useState(true);
  const [hitTarget, setHitTarget] = useState("not inspected");
  const inspect = () => {
    const button = actionRef.current;
    if (!button) return;
    const box = button.getBoundingClientRect();
    const hit = document.elementFromPoint(
      box.left + box.width / 2,
      box.top + box.height / 2,
    );
    setHitTarget(hit?.getAttribute("data-screen-layer") ?? "unknown");
  };

  return (
    <section className="screen-lab" aria-labelledby="screen-lab-heading">
      <div className="screen-copy">
        <p className="eyebrow">SCREEN STATE LAB</p>
        <h2 id="screen-lab-heading">Three views of one button</h2>
        <p>
          The DOM and accessibility tree expose an enabled action. Pixels and
          hit testing show that a synchronizing overlay blocks it.
        </p>
        <div className="screen-actions">
          <button className="quiet" onClick={inspect}>Inspect hit target</button>
          <button className="quiet" onClick={() => setBlocked(false)}>
            Finish synchronization
          </button>
          <button className="quiet" onClick={() => {
            setBlocked(true);
            setHitTarget("not inspected");
          }}>
            Reset mismatch
          </button>
        </div>
      </div>
      <div className="mock-window" aria-label="Example application window">
        <div className="window-bar"><i /><i /><i /><span>Release desk</span></div>
        <div className="window-body">
          <p>Candidate build</p>
          <strong>multimodal-studio-42</strong>
          <button
            ref={actionRef}
            className="deploy-action"
            data-screen-layer="deploy button"
          >
            Deploy build
          </button>
          {blocked && (
            <div className="sync-overlay" data-screen-layer="sync overlay">
              <span className="spinner" aria-hidden="true" />
              Synchronizing release state
            </div>
          )}
        </div>
      </div>
      <dl className="screen-signals">
        <div><dt>Pixels</dt><dd>{blocked ? "button occluded" : "button visible"}</dd></div>
        <div><dt>DOM</dt><dd>button disabled=false</dd></div>
        <div><dt>Accessibility</dt><dd>button “Deploy build”</dd></div>
        <div><dt>Hit test</dt><dd>{hitTarget}</dd></div>
      </dl>
    </section>
  );
}

const steps = ["Source", "Obligation", "Control", "Evidence", "Review", "Action"];

/** A code-native trace board; every step remains readable without animation. */
export default function TraceScene() {
  return <figure className="trace-scene">
    <div className="scene-caption"><span>THE COMPLIANCE CHAIN</span><span>01 — 06</span></div>
    <div className="trace-board" aria-hidden="true">
      <div className="trace-board-source">
        <span className="trace-board-index">01 / SOURCE</span>
        <svg viewBox="0 0 72 80" fill="none"><path d="M14 6h30l16 16v52H14V6Z" fill="white" stroke="currentColor" strokeWidth="3" /><path d="M44 6v16h16M24 36h26M24 46h26M24 56h16" stroke="currentColor" strokeWidth="3" /></svg>
        <strong>Start with<br />the source.</strong>
      </div>
      <div className="trace-board-link">↗</div>
      <div className="trace-board-decision">
        <span className="trace-board-index">06 / ACTION</span>
        <span className="trace-check">✓</span>
        <strong>A decision<br />you can explain.</strong>
      </div>
      <span className="trace-board-seal">HUMAN<br />REVIEWED</span>
    </div>
    <figcaption>{steps.map((step, i) => <span className="chain-step" key={step}><b>{String(i + 1).padStart(2, "0")}</b>{step}</span>)}</figcaption>
  </figure>;
}

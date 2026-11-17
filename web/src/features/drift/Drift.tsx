import { AnimatePresence, motion as m } from "framer-motion";
import { useState } from "react";
import { motion } from "../../app/theme";
import type { MonitorWindow } from "../../shared/types";
import { Empty } from "../../shared/ui";
import "./drift.css";

const pct = (x: number) => `${(100 * x).toFixed(1)}%`;

/** Three windows of searches as on-call saw them: a normal week, the week the wording drifted, after retraining. */
export function Drift({ windows }: { windows: MonitorWindow[] }) {
  const [open, setOpen] = useState(() => Math.max(0, windows.findIndex((w) => w.alerts.length > 0)));
  if (!windows.length) return <Empty>No monitor run yet. python3 scripts/monitor.py writes one.</Empty>;
  const w = windows[open];
  return (
    <div className="drift">
      <ol className="drift-steps" aria-label="Monitor windows">
        {windows.map((x, i) => (
          <li key={x.window}>
            <button className={`drift-step${i === open ? " on" : ""}${x.alerts.length ? " alarm" : ""}`}
              aria-pressed={i === open} onClick={() => setOpen(i)}>
              <span className="drift-when">{x.window}</span>
              <span className="drift-reader">reader {x.reader}</span>
              <span className="drift-flag">{x.alerts.length ? `${x.alerts.length} alerts` : "quiet"}</span>
            </button>
          </li>
        ))}
      </ol>
      <AnimatePresence mode="wait">
        <m.div key={w.window} className="panel drift-detail" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }} transition={{ duration: motion.duration, ease: motion.ease }}>
          <dl className="drift-stats">
            <div><dt>Novel wording</dt><dd>{pct(w.novel_share)}</dd><span>of sentences read</span></div>
            <div><dt>Confidence PSI</dt><dd>{w.confidence_psi ?? "–"}</dd><span>against the release baseline</span></div>
            <div><dt>Fallback calls</dt><dd>{w.fallback_calls_per_search}</dd><span>per search</span></div>
            <div><dt>Cost</dt><dd>${w.usd_per_search.toFixed(4)}</dd><span>per search</span></div>
          </dl>
          {w.alerts.length ? (
            <ul className="drift-alerts" aria-label="Alerts">
              {w.alerts.map((a) => <li key={a}>{a}</li>)}
              {w.retrain && <li className="next">Starts the retraining workflow: harvest, train, gate, promote.</li>}
            </ul>
          ) : <p className="muted">No check crossed its limit over {w.searches} searches.</p>}
        </m.div>
      </AnimatePresence>
    </div>
  );
}

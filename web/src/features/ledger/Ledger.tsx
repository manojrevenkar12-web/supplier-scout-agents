import { motion as m } from "framer-motion";
import { AUTOPILOT, motion } from "../../app/theme";
import type { Row } from "../../shared/types";
import { Empty } from "../../shared/ui";
import "./ledger.css";

/** The same cases through three designs. The autopilot's column is the one in colour. */
export function Ledger({ designs, rows }: { designs: string[]; rows: Row[] }) {
  if (!rows.length) return <Empty>No run yet. python3 scripts/evaluate.py writes one.</Empty>;
  return (
    <div className="ledger panel" role="table" aria-label="Three designs on the same RFQs">
      <div className="ledger-row ledger-head" role="row">
        <span role="columnheader">Same RFQs, same suppliers</span>
        {designs.map((d, i) => <span role="columnheader" key={d} className={i === AUTOPILOT ? "ours" : ""}>{d}</span>)}
      </div>
      {rows.map((r, i) => (
        <m.div key={r.label} className="ledger-row" role="row" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * motion.stagger, duration: motion.duration, ease: motion.ease }}>
          <span role="cell" className="label">{r.label}<small>{r.note}</small></span>
          {r.values.map((v, j) => <span role="cell" key={j} className={`value${j === AUTOPILOT ? " ours" : ""}`}>{v}</span>)}
        </m.div>
      ))}
    </div>
  );
}

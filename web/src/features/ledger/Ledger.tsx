import { motion as m } from "framer-motion";
import type { CSSProperties } from "react";
import { motion } from "../../app/theme";
import type { Row } from "../../shared/types";
import { Empty } from "../../shared/ui";
import "./ledger.css";

/** The same RFQs through each design. The design in production is the column in colour. */
export function Ledger({ designs, rows, ours, label }: { designs: string[]; rows: Row[]; ours: number; label: string }) {
  if (!rows.length) return <Empty>No run yet. python3 scripts/evaluate.py writes one.</Empty>;
  const cols = { "--cols": designs.length } as CSSProperties;
  return (
    <div className="ledger panel" role="table" aria-label={label} style={cols}>
      <div className="ledger-row ledger-head" role="row">
        <span role="columnheader">Same RFQs, same suppliers</span>
        {designs.map((d, i) => <span role="columnheader" key={d} className={i === ours ? "ours" : ""}>{d}</span>)}
      </div>
      {rows.map((r, i) => (
        <m.div key={r.label} className="ledger-row" role="row" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * motion.stagger, duration: motion.duration, ease: motion.ease }}>
          <span role="cell" className="label">{r.label}{r.note && <small>{r.note}</small>}</span>
          {r.values.map((v, j) => <span role="cell" key={j} className={`value${j === ours ? " ours" : ""}`}>{v}</span>)}
        </m.div>
      ))}
    </div>
  );
}

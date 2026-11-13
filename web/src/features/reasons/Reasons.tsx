import { Empty } from "../../shared/ui";
import "./reasons.css";

/** Why searches failed, per design: the same RFQs, counted against the truth. */
export function Reasons({ reasons }: { reasons: Record<string, Record<string, number>> }) {
  const entries = Object.entries(reasons);
  if (!entries.length) return <Empty>No run yet. python3 scripts/evaluate.py writes one.</Empty>;
  const max = Math.max(1, ...entries.flatMap(([, r]) => Object.values(r)));
  return (
    <div className="reasons">
      {entries.map(([design, r]) => (
        <div key={design} className="panel design">
          <h3>{design}</h3>
          {Object.keys(r).length === 0 ? <p className="muted">No search failed.</p> : (
            <ul>
              {Object.entries(r).map(([why, n]) => (
                <li key={why}>
                  <span className="why">{why}</span>
                  <span className="track" aria-hidden="true"><i style={{ width: `${(100 * n) / max}%` }} /></span>
                  <span className="n">{n}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

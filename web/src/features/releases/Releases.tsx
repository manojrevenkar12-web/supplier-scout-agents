import type { Release } from "../../shared/types";
import { Empty } from "../../shared/ui";
import "./releases.css";

const pct = (x: number) => `${(100 * x).toFixed(1)}%`;

/** Every reader in the registry, what it was trained on, and the gate it had to pass to reach production. */
export function Releases({ releases }: { releases: Release[] }) {
  if (!releases.length) return <Empty>No reader in the registry yet. Train one and run scripts/gate.py.</Empty>;
  return (
    <div className="releases">
      {releases.map((r) => (
        <article key={r.version} className={`panel release${r.production ? " live" : ""}`}>
          <header>
            <h3>{r.version}</h3>
            <span className={`tag ${r.passed ? "pass" : "fail"}`}>{r.production ? "in production" : r.passed ? "passed its gate" : "failed its gate"}</span>
          </header>
          <p className="muted">{r.corpora.join(" + ")}, {r.sentences.toLocaleString("en")} labelled sentences</p>
          <dl>
            <div><dt>Validation accuracy</dt><dd>{pct(r.accuracy)}</dd></div>
            <div><dt>Calibration error</dt><dd>{r.ece}</dd></div>
            <div><dt>Size, int8</dt><dd>{r.int8_kb.toLocaleString("en")} KB</dd></div>
            <div><dt>int8 reads like PyTorch</dt><dd>{pct(r.parity)}</dd></div>
          </dl>
          {r.checks.length > 0 && (
            <ul className="checks" aria-label={`Gate of ${r.version}`}>
              {r.checks.map((c) => (
                <li key={c.check} className={c.passed ? "ok" : "bad"}>
                  <span>{c.check}</span><span className="num">{String(c.value)}</span><span className="lim">{c.limit}</span>
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}

import { Drift } from "../features/drift/Drift";
import { Ledger } from "../features/ledger/Ledger";
import { Reasons } from "../features/reasons/Reasons";
import { Releases } from "../features/releases/Releases";
import { useConsole } from "../shared/api";
import { ErrorState, Section, Skeleton } from "../shared/ui";

export function App() {
  const { data, isPending, error, refetch } = useConsole();
  return (
    <main className="page">
      <header className="masthead">
        <h1><span>A shortlist you can</span><span>send to purchasing.</span></h1>
        <p>
          The same RFQs searched five ways, from one retrieval pass to an agent whose trained reader decides what each
          supplier's page says and asks the model only about the sentences it has not seen the like of.
        </p>
      </header>
      {isPending ? <Skeleton rows={6} /> : error ? <ErrorState message={error.message} onRetry={() => refetch()} /> : (
        <>
          <Ledger designs={data.designs} rows={data.ledger} ours={data.ours} label="Five designs on the same RFQs" />
          <Section id="reasons" title="Why searches failed"
            lede="A search fails if its shortlist holds a supplier that cannot supply, holds one company twice, or is shorter than it had to be. Counted against the truth.">
            <Reasons reasons={data.reasons} />
          </Section>
          <Section id="drift" title="When suppliers start saying things differently"
            lede="Six months later a quarter of the facts are worded in ways no reader was trained on. The monitor sees it in the reader's confidence before searches fail, and the labels production already paid for train the next reader.">
            <Drift windows={data.monitor} />
            <Ledger designs={data.drift.designs} rows={data.drift.rows} ours={data.drift.ours} label="Designs on the drifted wording" />
          </Section>
          <Section id="releases" title="Readers in the registry"
            lede="A reader reaches production only through its gate: its card, the agent on the dev world, and no regression on the drifted world.">
            <Releases releases={data.releases} />
          </Section>
          <p className="muted">Generated from {data.generated_from}.</p>
        </>
      )}
    </main>
  );
}

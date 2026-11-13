import { Ledger } from "../features/ledger/Ledger";
import { Reasons } from "../features/reasons/Reasons";
import { useConsole } from "../shared/api";
import { ErrorState, Section, Skeleton } from "../shared/ui";

export function App() {
  const { data, isPending, error, refetch } = useConsole();
  return (
    <main className="page">
      <header className="masthead">
        <h1><span>A shortlist you can</span><span>send to purchasing.</span></h1>
        <p>
          The same RFQs searched three ways: retrieval and one model pass, an agent that trusts what the model says
          about each supplier, and the agent that checks every claim against the supplier's own page.
        </p>
      </header>
      {isPending ? <Skeleton rows={6} /> : error ? <ErrorState message={error.message} onRetry={() => refetch()} /> : (
        <>
          <Ledger designs={data.designs} rows={data.ledger} />
          <Section id="reasons" title="Why searches failed"
            lede="A search fails if its shortlist holds a supplier that cannot supply, holds one company twice, or is shorter than it had to be. Counted against the truth.">
            <Reasons reasons={data.reasons} />
          </Section>
          <p className="muted">Generated from {data.generated_from}.</p>
        </>
      )}
    </main>
  );
}

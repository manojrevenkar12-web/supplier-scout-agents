# 3. Retrain from what production already paid for, behind a gate

## Context
Wording drifts. Labelling sentences by hand every month does not scale; the fallback answers production buys are
exactly the sentences the reader did not know.

## Decision
The monitor tracks novel wording, the population stability index of the reader's confidence against its release
baseline, fallback calls and cost per search. When drift crosses a limit (or weekly), the Argo workflow harvests the
agreed fallback answers, trains a candidate on the base corpus plus all harvests, and runs the gate: card checks, the
agent on the dev world against the 1% target and cost limit, and no regression against production on the drifted
world. Only a passing candidate is promoted and published; the API pods load the reader in production from GCS.

## Consequences
The cost of new wording falls back after one retraining. The gate's drift world must be refreshed from recent
traffic, or it stops representing what production sees. A shared model error in both readings is learned.

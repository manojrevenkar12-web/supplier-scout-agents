# supplier-scout-agents

**LangGraph agents that turn a buyer's RFQ into a shortlist of suppliers who can really make the part.** For
direct procurement: CNC-machined housings, die-cast brackets, cable harnesses, from manufacturers with the right
certificates, in the right region, with the capacity.

The agent plans the RFQ into requirements, retrieves candidates with hybrid search (BM25 and character n-grams,
fused by rank, filtered by region), qualifies each page with the model, and checks every claim in code: the
certificate must be quoted from the page and not marked expired, the process must still be offered, a sentence must
say the company makes the part itself, the capacity must be enough. When too few qualify it reflects and widens the
search in both languages. Shortlists are de-duplicated across domains and spellings, ranked by code, and a person is
asked about suppliers whose pages leave a hard requirement open (LangGraph interrupt). It runs behind FastAPI, with
searches on Pub/Sub, and on Cloud Run in the Terraform.

![The console: three designs on the same RFQs, why searches failed](docs/console.png)

## Measured against the truth

`src/scout/world/` simulates a supplier web: companies in fourteen countries, pages in English and German,
traders that present themselves as manufacturers (some without any of the usual words), certificates that expired,
processes no longer offered, the same company under a second domain, pages that address AI assistants, and a stand-in
model with known error rates. Every RFQ has the truth about which companies can supply it. A search **fails** if its
shortlist holds a supplier that cannot supply, holds one company twice, or is shorter than it had to be.

<!-- results:start -->
| | Single-shot RAG | Agent, claims trusted | Agent, claims checked |
|---|---:|---:|---:|
| Searches that failed <br><sub>of 500 RFQs; target under 1.0%</sub> | 98.0% | 74.8% | **0.2%** |
| Shortlisted suppliers that really qualify <br><sub>precision of the shortlist</sub> | 15.2% | 71.4% | **100.0%** |
| Qualified suppliers found <br><sub>of the shortlist size, or of all that exist when fewer</sub> | 12.2% | 76.4% | **100.0%** |
| Shortlisted suppliers that cannot supply <br><sub>expired certificates, traders, discontinued processes, capacity</sub> | 550 | 701 | **0** |
| The same company twice in a shortlist <br><sub>one company under two domains or spellings</sub> | 32 | 0 | **0** |
| Suppliers shortlisted because their page told the AI to <br><sub>pages addressing AI assistants</sub> | 30 | 26 | **0** |
| Model calls per search <br><sub>one for the plan, one per page qualified</sub> | 31 | 46.2 | **63.3** |
| Cost per search <br><sub>Sonnet-class list prices, from token counts</sub> | $0.073 | $0.109 | **$0.150** |

- **World:** 1,800 companies on 1,948 pages (some under two domains), in English and German; 500 RFQs with the truth about who can supply each.
- **Sent to a person:** 0.85 suppliers per search on average, where capacity or own production is not stated; they are asked about, not shortlisted.
<!-- results:end -->

The held-out world (another seed and size) was run once after the code was frozen, at the commit in
`config/heldout.lock`. CI fails if the dev world's failure rate is not under the target.

## How it is built

| | | |
|---|---|---|
| **Graph** | plan → retrieve → qualify → reflect (loop) → shortlist → human review | `src/scout/graph.py` |
| **Plan** | the model writes the requirements; code reads certificates from the RFQ text and adds any the plan dropped | `graph.py` |
| **Retrieval** | BM25 + TF-IDF on character n-grams (German compounds, spelling), reciprocal rank fusion, region filter before ranking; widened in rounds with synonyms in both languages | `src/scout/index.py`, `taxonomy.py` |
| **Checks** | quoted evidence, expiry and discontinuation in the same sentence, distributors, own production, region, capacity | `src/scout/verify.py` |
| **Pages are data** | sentences addressed to AI systems removed before the model reads | `verify.py` |
| **One company, one row** | names normalised across umlauts, English and German words, legal forms | `src/scout/entities.py` |
| **Cost** | code drops pages that cannot qualify before a model call; a page is qualified once per search; a budget per search | `graph.py`, `config/scout.toml` |
| **Service** | FastAPI, Pub/Sub (idempotent on redelivery), interrupt and resume for review | `src/scout/service/` |
| **GCP** | Cloud Run API and worker, Pub/Sub with dead letters, Firestore, Secret Manager, a log-based failure metric with an alert | `infra/terraform/` |

## Run it

```bash
pip install -e '.[dev]'
pytest -q
python3 scripts/evaluate.py      # the three designs, about 30 seconds
python3 scripts/readme.py        # README results and web/public/data/console.json
cd web && npm ci && npm run dev
```

## Limits

* The numbers come from a simulation: the supplier pages, the error rates of the stand-in model and the RFQs are
  assumptions in `config/world.toml`. The Claude adapter is tested against a recorded answer, not run here.
* The checks read English and German phrasing they were written for; a real supplier web says the same things in
  more ways, and every new way is a new check or a question for a person.
* Search state lives in the process; the Firestore store named in the Terraform is the next step. The Terraform is
  validated in CI, not applied.

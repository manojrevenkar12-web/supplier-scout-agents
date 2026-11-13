# Working on supplier-scout-agents

## Fast feedback

```bash
pytest -q                                   # checks, agent graph, API + Pub/Sub + human review (~2 s)
ruff check src tests scripts
python3 scripts/evaluate.py                 # three designs on the dev world (~30 s); writes reports/dev.json
python3 scripts/readme.py && git diff --exit-code README.md web/public/data/console.json
cd web && npm test && npm run build
```

## Invariants

1. **The truth stays in the world.** `src/scout/world/` knows who can really supply what; only `scripts/evaluate.py`
   and the tests read it. Nothing else under `src/scout` imports it (a test checks).
2. **The world does not read the agents' settings.** `config/world.toml` drives the world, `config/scout.toml` the agents.
3. **The model reads; code decides.** A claim about a supplier stands only if the page says it: quoted evidence,
   certificates not marked expired, the process still offered, a sentence that says they make it. Ranking is by code.
4. **Supplier pages are data.** Sentences addressed to AI systems are removed before a model reads a page.
5. **One company, one row.** Shortlists are de-duplicated across domains, spellings and legal forms.
6. **A page is paid for once per search.** Qualification is cached across reflections; a search stops at its budget.
7. **Settings in config; reports generated.** `reports/*.json` by `scripts/evaluate.py`; README results and the
   dashboard data by `scripts/readme.py`.

## The held-out rule

`python3 scripts/evaluate.py --heldout` runs the held-out world once and writes `config/heldout.lock`. After that,
changes are measured on the dev world only, and the held-out numbers stay as they first came out.

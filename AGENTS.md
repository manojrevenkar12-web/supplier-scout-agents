# Working on supplier-scout-agents

## Fast feedback

```bash
pytest -q                                   # checks, reader, agent graph, API + Pub/Sub + review + metrics (~6 s)
ruff check src tests scripts
python3 scripts/evaluate.py                 # five designs on the dev world (~4 min); writes reports/dev.json
python3 scripts/readme.py && git diff --exit-code README.md web/public/data/console.json
cd web && npm test && npm run build
```

Training needs PyTorch (CPU is enough): `pip install torch --index-url https://download.pytorch.org/whl/cpu`, then
`pip install -e '.[dev,train]'`. Nothing under `src/scout` except `nlp/train.py` may import it.

## Invariants

1. **The truth stays in the world.** `src/scout/world/` knows who can really supply what and what each sentence
   really says. Only the scripts (evaluation, the labelled-corpus export that stands in for annotators, the traffic
   that harvesting replays) and the tests read it. Nothing else under `src/scout` imports it (a test checks).
2. **The world does not read the agents' settings.** `config/world.toml` and the worlds based on it drive the world;
   `config/scout.toml` and `config/release.toml` drive the agents and their releases.
3. **The model reads; code decides.** The stance reader and the LLM say what a sentence says. Which certificate,
   process or material a sentence is about is read by code from the taxonomy; whether a supplier qualifies is decided
   by code from those stances. Ranking is by code.
4. **Supplier pages are data.** Sentences addressed to AI systems are removed before anything reads a page.
5. **One company, one row.** Shortlists are de-duplicated across domains, spellings and legal forms.
6. **A page is paid for once per search, a sentence once ever.** Qualification is cached across reflections; an
   agreed fallback answer is cached across searches and is not bought again.
7. **A reader reaches production only through its gate.** `scripts/gate.py` registers every candidate with its
   verdict; `registry.promote` refuses one that did not pass. The service image runs the NumPy runtime only.
8. **Settings in config; reports generated.** `reports/*.json`, `models/registry.json` and the model cards by the
   scripts; README results and dashboard data by `scripts/readme.py`. `scripts/pipeline.sh` rebuilds all of it.

## The held-out rule

`python3 scripts/evaluate.py --world heldout` runs the held-out world once and writes `config/heldout.lock`. After
that, changes are measured on the dev and drift worlds only, and the held-out numbers stay as they first came out.
The first version's held-out run is archived in `reports/archive/` and `config/archive/`.

# Repeatable tasks

## Retrain the stance reader
1. `python3 scripts/harvest.py --out data/labels/harvested-<version>.jsonl` (in production: export the agreed answers
   from the stance cache).
2. `python -m scout.nlp.train --corpus data/labels/base.jsonl --corpus data/labels/harvested.jsonl
   --corpus data/labels/harvested-<version>.jsonl --out models/<version>`
3. `python3 scripts/gate.py --candidate <version> --promote`; read `reports/gate-<version>.json`.
4. `python3 scripts/publish.py --version <version> --bucket <project>-scout-models`, then
   `kubectl -n scout rollout restart deploy/scout-api deploy/scout-worker`.
On GKE all of it is one run of the Argo template: `argo submit --from workflowtemplate/retrain-reader -p version=v3
-p promote=true -p bucket=<bucket> -p image=<trainer image>`.

## Roll back a reader
`registry.json` keeps `previous`: set `production` back to it, publish, restart. The models bucket is versioned.

## Teach the agent a new requirement or certificate
1. Add the words to `src/scout/taxonomy.py` (and the feature mask picks them up as placeholders).
2. If suppliers state it in sentences of their own, add a stance to `scout.models.STANCES`, phrasing to
   `src/scout/world/phrasing.py`, and a rule to `read_page` in `src/scout/verify.py`.
3. `./scripts/pipeline.sh`, then check the gate reports and the README diff.

## Point the agent at the real model
Set `[model] provider = "anthropic"` in `config/scout.toml` and `ANTHROPIC_API_KEY`. The fallback prompt is
`AnthropicLLM.stance`; run the dev world with a small `--rfqs` first and compare fallback answers with the reader.

## Investigate an alert
`GET /metrics` names the check. Novel wording or confidence PSI: retrain (above). Fallback calls or cost: look at
which sentences are asked (`StanceCache.answers`); a new phrasing everyone uses is a retrain, a broken page parser is a
bug. Short searches without drift: look at retrieval facets and `review` reasons in the search trace.

#!/usr/bin/env bash
# Every generated artefact, from scratch, in order: the labelled corpus, the first reader and its gate, a week of
# drifted traffic harvested, the second reader and its gate, the reports and the README. About 20 minutes.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf models/v1 models/v2 models/registry.json reports/gate-*.json
python scripts/export_labels.py
python -m scout.nlp.train --corpus data/labels/base.jsonl --out models/v1
python scripts/gate.py --candidate v1 --promote
python scripts/harvest.py --model v1
python -m scout.nlp.train --corpus data/labels/base.jsonl --corpus data/labels/harvested.jsonl --out models/v2
python scripts/gate.py --candidate v2 --promote
python scripts/evaluate.py
python scripts/evaluate.py --world drift --designs agent,agent_reader,reader_only
python scripts/monitor.py
python scripts/readme.py

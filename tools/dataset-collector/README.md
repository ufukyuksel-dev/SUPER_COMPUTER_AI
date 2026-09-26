# dataset-collector

Rights-aware, resumable data collection with provenance, rate limiting, dedup and leakage-safe split checks
(imported from AI_Developer `scripts/collector/`, 2026-09-25). Used by the `training-data-engineering` skill and the
`dataset-curator` role.

```sh
cd tools/dataset-collector
python3 -m collector.collect <source_id>            # sources: config/sources.yaml, output: data/
python3 -m collector.slots <routing.yaml> <slot> "<prompt>"   # usage log: state/slot-usage.jsonl
python3 -m pytest tests -q                          # requires PyYAML + pytest (requirements-dev.txt)
```

`data/` and `state/` are local runtime output and are git-ignored. `config/sources.yaml` must reference only public
sources; credentials, if a source ever needs them, come from the environment, never from this directory.

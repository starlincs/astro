# Astro

CLI tool and library for CSV import pipelines.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
astro --help
astro ingest path/to/data.csv
astro ingest path/to/data/
astro run
astro list
astro cleanup
```

Pipeline repos define a `pipeline.py` that imports Astro and exports a `pipeline` instance. Run Astro from that directory (or pass `-C`).

See [SPEC.md](SPEC.md) for the full behavioural specification.

## Development

```bash
make check          # lint + format + typecheck + tests
make fix            # auto-fix lint and format issues
pre-commit install  # optional: run hooks on commit
pre-commit run -a   # run all hooks manually
```

Optional pre-push hook:

```bash
pre-commit install --hook-type pre-push
```

## Project layout

```text
src/astro/     Library and CLI
tests/         pytest suite
examples/      Sample pipeline.py
```

# Astro

CLI tool and library for CSV import pipelines.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
astro --help
astro ingest path/to/data/
astro run
astro run --mode cli
astro run --run-id abc12
astro describe
astro list
astro cleanup
```

`astro ingest` prints logs to the console and writes them to `.working/{run_id}/astro.log`. `astro run` executes registered pipeline steps; it uses a Rich dashboard by default (`--mode cli` for plain log output). Steps use `AstroFileSpec` / `AstroFile` containers with explicit output paths. Use `add_filter` for declarative row filtering; re-run `astro run` against a `quarantined` run to merge quarantined rows back and retry only the affected steps. Record custom metrics from steps via `ctx.stats`.

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

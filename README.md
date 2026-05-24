# Astro

CLI tool and library for CSV import pipelines.

## Documentation

Full documentation is hosted at **[https://astro.readthedocs.io](https://astro.readthedocs.io)**.

Build locally with `pip install -e ".[docs]"` and `make docs`.

## Install

From PyPI:

```bash
pip install astro-pipeline
```

The package installs the `astro` CLI and Python module. PyPI name is `astro-pipeline` because `astro` is already taken.

From source:

```bash
git clone https://github.com/starlincs/astro.git
cd astro
pip install -e ".[dev]"
```

## What Astro does

Astro ingests CSV directories into validated Parquet snapshots, then runs ordered pipeline steps with statistics, filtering, and row quarantine. Each pipeline lives in an external repository as a `pipeline.py` file.

```text
External repo (pipeline.py)  →  astro ingest  →  .working/{run_id}/ingested/
                              →  astro run     →  processed outputs + stats
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
astro cleanup --dry-run
astro cleanup --yes
```

`astro ingest` prints logs to the console and writes them to `.working/{run_id}/astro.log`. `astro run` executes registered pipeline steps; it uses a Rich dashboard by default (`--mode cli` for plain log output). Set `step_execution_mode = StepExecutionMode.PARALLEL` on a pipeline to run independent steps concurrently (subject to `depends_on` and shared-file locking). Large files (≥100MB by default) use batched ingest, filter, and quarantine I/O; steps can also use `file.scan()` and `file.sink()` for lazy transforms. Steps use `AstroFileSpec` / `AstroFile` containers with explicit output paths. Use `add_filter` for declarative row filtering; re-run `astro run` against a `quarantined` run to merge quarantined rows back and retry only the affected steps. Record custom metrics from steps via `ctx.stats`.

**Filter caveat:** filter steps split rows using joins on all columns. Identical duplicate rows may not partition cleanly if the filter returns fewer copies than exist in the input.

Pipeline repos define a `pipeline.py` that imports Astro and exports a `pipeline` instance. Run Astro from that directory (or pass `-C`).

See [SPEC.md](SPEC.md) for the full behavioural specification (for implementers). User-facing guides live in [docs/](docs/). A runnable example is in [examples/](examples/).

## Security model

Astro loads and executes `pipeline.py` from the working directory you point it at. Only run Astro against pipeline repositories you trust. Pipeline code runs with your user permissions and can read and write files under the pipeline directory.

## Development

```bash
make check          # lint + format + typecheck + tests
make cov            # include large-file integration tests
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
docs/          Sphinx documentation source
```

## License

MIT — see [LICENSE](LICENSE).

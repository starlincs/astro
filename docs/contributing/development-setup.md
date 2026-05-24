# Development setup

## Prerequisites

- Python 3.11 or later
- Git

## Install

```bash
git clone <repository-url>
cd astro
pip install -e ".[dev]"
```

Verify the CLI:

```bash
astro --help
```

## Canonical commands

```bash
make check                              # lint + format + typecheck + tests
make fix                                # auto-fix lint and format issues
pytest tests/path/to/test_module.py -q  # run a single test module
pre-commit run -a                       # run all pre-commit hooks
```

Always run `make check` before finishing a task.

## Pre-commit hooks

Install hooks to run lint, format, and type checks on commit:

```bash
pre-commit install
```

Optional pre-push hook to run tests:

```bash
pre-commit install --hook-type pre-push
```

Full pytest runs via `make check`, not pre-commit (too slow for every commit).

## Project structure

| Directory | Purpose |
|-----------|---------|
| `src/astro/cli/` | Typer CLI entry point and display |
| `src/astro/ingest/` | Ingest service and materialization |
| `src/astro/pipeline/` | Pipeline contract and file containers |
| `src/astro/run/` | Run service and scheduler |
| `src/astro/filter/` | Filter step executor |
| `src/astro/quarantine/` | Quarantine store and collector |
| `src/astro/resolver/` | Canonical ID resolver |
| `src/astro/stats/` | Statistics recorder |
| `src/astro/storage/` | SQLite pipeline store |
| `src/astro/working/` | Run manager and manifest |
| `src/astro/io/` | CSV/Parquet streaming helpers |

## Next steps

- {doc}`testing` — test-first workflow
- {doc}`code-style` — linting and formatting conventions

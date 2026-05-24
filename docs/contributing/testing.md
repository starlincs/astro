# Testing

Astro uses pytest with pytest-cov. Coverage must remain at or above 80%.

## Test-first workflow

1. Read the relevant section of `SPEC.md`
2. Add or update a failing test in `tests/`
3. Run `pytest path/to/test.py` and confirm it fails for the expected reason
4. Implement the minimal change in `src/astro/`
5. Run `make check` and confirm all gates pass

Do not implement features without a failing test first. Do not skip tests because a command is a stub.

## Test layout

| Directory | Purpose |
|-----------|---------|
| `tests/cli/` | Typer CLI tests using `CliRunner` |
| `tests/pipeline/` | Discovery and `Pipeline` contract |
| `tests/ingest/` | Ingest service and materialization |
| `tests/run/` | Run service, parallel execution, quarantine |
| `tests/filter/` | Filter executor and store |
| `tests/quarantine/` | Quarantine store |
| `tests/io/` | Large-file streaming |
| `tests/storage/` | `PipelineStore` behaviour |
| `tests/resolver/` | Canonical ID resolver |
| `tests/stats/` | Statistics recorder |
| `tests/test_import.py` | Package smoke tests |

## Running tests

```bash
make test                    # full suite with coverage
pytest tests/cli/ -q         # single directory
pytest -k "test_ingest" -q   # by name pattern
make cov-html                # HTML coverage report
```

## Markers

Mark slow or fixture-heavy tests:

```python
@pytest.mark.integration
def test_full_pipeline_run():
    ...
```

Large-file integration tests use `@pytest.mark.large` and are excluded from the default `make check` run.

## Coverage

Configuration in `pyproject.toml`:

- Minimum coverage: 80%
- Branch coverage enabled
- Source: `src/astro`

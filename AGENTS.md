# AGENTS.md

Instructions for coding agents working on Astro.

## Canonical commands

```bash
pip install -e ".[dev]"
make check
pytest tests/path/to/test_module.py -q
pre-commit run -a
```

Always run `make check` before finishing a task.

## Source of truth

Use [SPEC.md](SPEC.md) for behavioural requirements. If implementation and spec disagree, update the spec only for clarifications—not substantive changes without explicit approval.

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
| `tests/storage/` | `PipelineStore` behaviour |
| `tests/test_import.py` | Package smoke tests |

Mark slow or fixture-heavy tests with `@pytest.mark.integration`.

## Code conventions

- Match existing module structure under `src/astro/`
- Use Ruff formatting (line length 100)
- Type-check with `ty check`
- Prefer `X | None` over `Optional[X]`

## Pre-commit hooks

Hooks run ruff, ty, and hygiene checks. Full pytest runs via `make check`, not pre-commit (too slow). An optional pre-push hook can run `make test`.

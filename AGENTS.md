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
5. Update user docs, `SPEC.md`, and `CHANGELOG.md` when behaviour changes (see `.cursor/rules/document-everything.mdc`)
6. Run `make check` and confirm all gates pass

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

## Cursor Cloud specific instructions

- **Virtual environment required for `ty`:** Packages must be installed inside a `.venv` at the workspace root. The `ty` type checker only resolves third-party imports from the venv's `site-packages`; user-level installs (`~/.local/`) are not searched. The update script handles venv creation and `pip install -e ".[dev]"`.
- **Activate before running commands:** Always run `. .venv/bin/activate` (or use `.venv/bin/` prefixed binaries) before `make check`, `pytest`, `astro`, `ruff`, or `ty`.
- **`python3.12-venv` apt package:** Required to create the venv. The update script installs it if missing.
- **No external services:** Astro is fully local — no Docker, databases, or network services needed. SQLite is stdlib. All tests use `tmp_path` fixtures.
- **Quality gate:** `make check` runs `ruff check`, `ruff format --check`, `ty check`, and `pytest` (with 80% coverage minimum). See `Makefile` for individual targets and `README.md` for the brief command list.
- **Example pipeline:** `examples/` contains a runnable pipeline. See `examples/README.md` for the hello-world walkthrough (`astro ingest`, `astro run`, `astro describe`, `astro list`, `astro cleanup`).

# Code style

## Formatting and linting

Astro uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

| Setting | Value |
|---------|-------|
| Line length | 100 |
| Target Python | 3.11 |

```bash
make lint      # check only
make format    # check formatting
make fix       # auto-fix lint and format
```

## Type checking

Astro uses [ty](https://github.com/astral-sh/ty) for static type checking:

```bash
make typecheck   # runs ty check
```

Type checking scope: `src/astro` (configured in `pyproject.toml`).

## Conventions

- Match existing module structure under `src/astro/`
- Prefer `X | None` over `Optional[X]`
- Use explicit imports; follow Ruff isort rules
- Keep changes minimal and focused

## Pre-commit

Pre-commit runs:

- Trailing whitespace and end-of-file fixes
- YAML validation
- Debug statement check
- Test naming (`test_*.py`)
- Ruff check (with auto-fix) and format
- ty type check

Install with `pre-commit install`.

## Per-file ignores

Configured in `pyproject.toml`:

- `tests/**` — allows assert statements and mutable class defaults
- `examples/**` — allows mutable class defaults

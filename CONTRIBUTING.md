# Contributing to Astro

Thank you for your interest in contributing.

## Development setup

```bash
git clone https://github.com/starlincs/astro.git
cd astro
pip install -e ".[dev]"
pre-commit install
```

## Workflow

Astro uses test-first development. Before changing `src/astro/`:

1. Read the relevant section of [SPEC.md](SPEC.md).
2. Add or update a failing test in `tests/`.
3. Run `pytest path/to/test.py` and confirm it fails for the expected reason.
4. Implement the minimal change in `src/astro/`.
5. Run `make check` before opening a pull request.

See [AGENTS.md](AGENTS.md) for agent-oriented instructions, [docs/contributing/](docs/contributing/) for detailed guides, and [docs/contributing/release.md](docs/contributing/release.md) for PyPI publishing.

## Quality gate

`make check` runs lint, format check, type check, and the full test suite with coverage (minimum 80%).

```bash
make check
make fix    # auto-fix lint and format issues
```

## Pull requests

- Keep changes focused and reviewable.
- Update [CHANGELOG.md](CHANGELOG.md) for user-visible changes.
- Update user docs in `docs/` and [SPEC.md](SPEC.md) when behaviour changes (see `.cursor/rules/document-everything.mdc`).
- Ensure CI passes.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

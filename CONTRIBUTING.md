# Contributing to Astro

Thank you for your interest in contributing.

The **canonical contributing guide** lives in the documentation site:

**[https://astro-pipeline.readthedocs.io/en/latest/contributing/index.html](https://astro-pipeline.readthedocs.io/en/latest/contributing/index.html)**

Source files are under [`docs/contributing/`](docs/contributing/).

## Quick start

```bash
git clone https://github.com/starlincs/astro.git
cd astro
pip install -e ".[dev]"
pre-commit install
make check
```

Before changing `src/astro/`, read the relevant section of [SPEC.md](SPEC.md), add a failing test, implement the fix, update user docs when behaviour changes, and run `make check`. See [AGENTS.md](AGENTS.md) for agent-oriented workflow.

## Repository docs

| File | Purpose |
|------|---------|
| [`docs/`](docs/) | User guides and API reference (Read the Docs) |
| [`SPEC.md`](SPEC.md) | Behavioural specification for implementers |
| [`AGENTS.md`](AGENTS.md) | Instructions for coding agents |
| [`CHANGELOG.md`](CHANGELOG.md) | User-visible release notes |
| [`SECURITY.md`](SECURITY.md) | Vulnerability reporting (GitHub security policy) |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards |

## Pull requests

- Keep changes focused and reviewable.
- Update [CHANGELOG.md](CHANGELOG.md) for user-visible changes.
- Ensure CI passes.

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

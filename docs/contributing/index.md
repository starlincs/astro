# Contributing

Thank you for contributing to Astro. This guide covers development setup, testing, code style, and documentation.

## Source of truth

| Audience | Location |
|----------|----------|
| End users | `docs/` (built with Sphinx, hosted on [Read the Docs](https://astro-pipeline.readthedocs.io)) |
| Implementers and agents | [`SPEC.md`](https://github.com/starlincs/astro/blob/main/SPEC.md) |
| Coding agents | [`AGENTS.md`](https://github.com/starlincs/astro/blob/main/AGENTS.md) |

Root-level markdown files exist for GitHub and tooling, not as a second copy of the user guides:

| Root file | Role |
|-----------|------|
| [`README.md`](https://github.com/starlincs/astro/blob/main/README.md) | Repository landing page — brief overview and links into `docs/` |
| [`CONTRIBUTING.md`](https://github.com/starlincs/astro/blob/main/CONTRIBUTING.md) | GitHub contributing entry point — points here |
| [`SECURITY.md`](https://github.com/starlincs/astro/blob/main/SECURITY.md) | GitHub security policy and vulnerability reporting |
| [`CHANGELOG.md`](https://github.com/starlincs/astro/blob/main/CHANGELOG.md) | Release notes |
| [`CODE_OF_CONDUCT.md`](https://github.com/starlincs/astro/blob/main/CODE_OF_CONDUCT.md) | Community standards |

When you change behaviour, update the relevant page in `docs/` and `SPEC.md`. Do not duplicate long-form guides in root markdown files.

## Quality bar

Before merging or completing work:

1. `make check` must pass (lint, format, typecheck, tests)
2. Test coverage must remain at or above 80%
3. New behaviour requires tests written first

## Project layout

```text
src/astro/     Library and CLI
tests/         pytest suite
docs/          Sphinx documentation
examples/      Sample pipeline.py
```

## Getting started

See {doc}`development-setup` for installation and {doc}`testing` for the test-first workflow.

When behaviour changes, update user docs and `SPEC.md` in the same change (see `.cursor/rules/document-everything.mdc`).

## Releasing

See {doc}`release` for version bumps, building wheels, and publishing to PyPI.

## Documentation

See {doc}`documentation` for building docs locally and publishing to Read the Docs.

## License

Astro is released under the MIT License. See `LICENSE` in the repository root.

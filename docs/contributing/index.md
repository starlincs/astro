# Contributing

Thank you for contributing to Astro. This guide covers development setup, testing, code style, and documentation.

## Source of truth

- **User documentation** — `docs/` (built with Sphinx, hosted on Read the Docs)
- **Behavioural specification** — `SPEC.md` (implementation contract for developers and agents)
- **Agent instructions** — `AGENTS.md` (coding agent workflow)

When you change behaviour, update `SPEC.md` and the relevant user guide pages in `docs/`. Keep them in sync.

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

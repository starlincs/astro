# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |

## Reporting a vulnerability

If you discover a security issue, please report it privately rather than opening a public issue.

1. Open a [GitHub Security Advisory](https://github.com/starlincs/astro/security/advisories/new) on this repository, or
2. Contact the maintainers through GitHub with minimal details and request a private channel.

Include:

- A description of the vulnerability and its impact
- Steps to reproduce
- Affected versions
- Any suggested fix, if available

We aim to acknowledge reports within 72 hours and provide a fix or mitigation plan as soon as practicable.

## Security model

Astro executes arbitrary Python from a `pipeline.py` file in the working directory. Only run Astro against pipeline repositories you trust. See the [security model](https://astro-pipeline.readthedocs.io/en/latest/getting-started/introduction.html#security-model) in the documentation for details.

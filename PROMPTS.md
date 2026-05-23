# Prompt templates

Reusable blocks for feature work prompts.

## TDD Always

```
Write tests first against SPEC.md requirements.
Confirm tests fail for the expected reason.
Implement the minimal code to pass.
Run `make check` before finishing.
```

## Feature prompt skeleton

```
<context>
Read SPEC.md for Astro architecture and requirements.

Implement: [describe feature]

## TDD Always
Write tests first, confirm red, implement, run `make check`.

## Specification as source of truth
Refer back to SPEC.md regularly. Do not change existing spec items substantively
without review.
</context>

<tasks>
1. [task]
</tasks>

<success>
Done when: tasks complete, `make check` passes, spec updated if needed for clarifications only.
</success>
```

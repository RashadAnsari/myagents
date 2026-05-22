---
name: code-reusability
description: Spot duplication and apply reusability patterns in code being written or reviewed. Activate when user asks to "improve reusability", "extract this", "reduce duplication", "refactor for reuse", or "DRY this up".
---

# Code Reusability Skill

When active, scan the code in context for duplication and reusability gaps, then apply the appropriate pattern. For a full codebase-wide audit, use the `code-reviewer` or `architecture-reviewer` agents instead.

## What to Look For

- Same logic copied in two or more places: extract to shared function or module
- Same validation rule written per handler: extract to single validator
- Same constants or thresholds defined in multiple files: move to single config or constants module
- Similar functions differing only by one value or type: parameterize or generalize
- Same object construction repeated inline: extract to factory or builder
- Same error mapping repeated per handler: extract to shared mapper
- Same test setup repeated per file: extract to shared factory or fixture

## Patterns to Apply

| Signal | Pattern |
|--------|---------|
| Same logic in 2+ places | Extract function / Extract module |
| Same logic with minor variation | Parameterize: add argument instead of copying |
| Same group of values always together | Introduce value object or struct |
| Same multi-step process repeated | Extract class or service |
| Same conditional type-switching | Replace with polymorphism or strategy |
| Same object built ad-hoc everywhere | Factory or builder function |
| Same config value hardcoded in N places | Named constant or config key |

## Rules

- Extract only when duplication is confirmed: two instances minimum before extracting
- Do not over-abstract: the extracted unit must be simpler to use than the original duplication
- Name the extracted unit after what it does, not where it came from
- Verify all call sites after extraction: do not leave dead copies behind
- Do not change behavior during extraction: pure structural refactor only

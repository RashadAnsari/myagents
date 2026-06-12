---
name: dev-conventions
description: 'Development conventions: think before coding, simplicity first, reuse and duplication discipline, surgical scope, localization, UI consistency, validation, data alignment, and verifiable success criteria. Activate when writing, reviewing, or refactoring code in any project, or when the user asks to "improve reusability", "reduce duplication", or "DRY this up".'
---

# Development Conventions

General rules that apply across all projects. Read and follow before making any code change.

**Tradeoff:** These rules bias toward caution over speed. For trivial tasks, use judgment.

## Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## Reuse Before Creating

- Before adding a component, helper, constant, service, or utility: search the codebase first
- If an equivalent already exists, import and reuse it
- Extend existing components with props or small local composition before creating variants
- Only add a helper, service, or shared constant when logic is reused across files or clearly belongs to an existing shared module
- If logic is local to one screen or form, keep it as a private local helper: do not extract prematurely

## No Duplication

- Shared business logic belongs in the project's shared service or domain layer
- Shared UI belongs in the project's shared widget or component layer
- Shared constants belong in the relevant domain file: not scattered per file
- Do not create a variant of something that already exists: parameterize or extend instead

When you spot duplication, apply the matching pattern:

| Signal | Pattern |
|--------|---------|
| Same logic in 2+ places | Extract function / Extract module |
| Same logic with minor variation | Parameterize: add argument instead of copying |
| Same group of values always together | Introduce value object or struct |
| Same multi-step process repeated | Extract class or service |
| Same conditional type-switching | Replace with polymorphism or strategy |
| Same object built ad-hoc everywhere | Factory or builder function |
| Same config value hardcoded in N places | Named constant or config key |
| Same validation rule written per handler | Extract to single validator |
| Same error mapping repeated per handler | Extract to shared mapper |
| Same test setup repeated per file | Extract to shared factory or fixture |

Extraction rules:

- Extract only when duplication is confirmed: two instances minimum before extracting
- Do not over-abstract: the extracted unit must be simpler to use than the original duplication
- Name the extracted unit after what it does, not where it came from
- Verify all call sites after extraction: do not leave dead copies behind
- Do not change behavior during extraction: pure structural refactor only

For a full codebase-wide audit, use the `code-reviewer` or `architecture-reviewer` agents instead.

## Surgical Changes & Scope Control

**Touch only what you must. Clean up only your own mess.**

- Make the requested change at the layer where it belongs
- Do not update downstream consumers, exports, reports, or unrelated screens unless the request explicitly requires it
- Don't "improve" adjacent code, comments, or formatting
- Don't refactor things that aren't broken
- Match existing style, even if you'd do it differently
- If you notice unrelated dead code, mention it - don't delete it

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused
- Don't remove pre-existing dead code unless asked

The test: Every changed line should trace directly to the user's request.

## Localization

- All user-facing strings must go through the project's i18n / localization system
- Never hardcode visible text in source code
- Add or update keys in all supported language files simultaneously
- Do not localize outputs that have a fixed statutory or legal format (invoices, official exports) unless explicitly instructed

## Copy & Punctuation

- No period on short labels, headings, button text, or single-phrase descriptions
- Use a period on full sentences: multi-clause warnings, FAQs, longer descriptions
- Put spaces around slashes between words in user-facing copy (`Make / model`): do not apply to paths, URLs, units, or technical tokens
- Never use the em dash in user-facing text: use a colon, comma, or period instead

## UI Consistency

Color tokens are named variables defined in the project's design system that reference specific colors (e.g., `primary`, `surface`, `error`, `on-primary`). They live in the theme configuration and must be referenced by name: never replaced with raw hex or RGB values.

- Always use the project's design system: theme, spacing scale, color tokens, typography
- Never invent colors, spacing values, or design tokens outside the established scale
- Never create a parallel design system or shadow theme
- Use the project's established spacing scale exactly: do not use off-scale values
- Destructive actions must use the error color from the theme
- Primary actions must use the primary or primary-container color from the theme
- Do not use hardcoded color values: always reference theme tokens

## Form & Validation

- Every required field label must end with ` *`
- Never add `(optional)` to optional field labels: absence of `*` already signals optional
- Show validation errors inline with the field: do not use toasts or snackbars for validation errors
- Validation messages must explain exactly what to enter and why: no generic "Required"
- Add a dedicated i18n key per validation message: do not reuse generic error strings
- When an optional field has a format constraint, allow empty values before checking format

## Data & Persistence Alignment

- Form fields and DB columns must stay in sync for nullability, type, defaults, and constraints
- Required form fields must map to non-null columns
- Optional form fields must map to nullable columns
- When adding a required field or changing nullability, add a migration: never silently break existing rows
- Derived or calculated fields: compute once during insert/update and persist: other readers use the stored value
- Enum or dropdown values stored in DB must use stable keys: never store display labels, never display raw keys to users

## Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Formatting & Verification

- After every code, localization, configuration, or documentation change: run the project's lint, format, and analysis commands
- Fix all reported issues before considering the change done
- Do not finish a task with failing lint, format warnings, or generated-code drift
- After changing localization or code-generation source files: regenerate output before running verification

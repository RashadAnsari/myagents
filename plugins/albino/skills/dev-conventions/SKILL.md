---
name: dev-conventions
description: 'General development conventions: reuse, scope discipline, localization, UI consistency, validation, and data alignment. Activate when writing or reviewing code in any project.'
---

# Development Conventions

General rules that apply across all projects. Read and follow before making any code change.

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

## Scope Control

- Make the requested change at the layer where it belongs
- Do not update downstream consumers, exports, reports, or unrelated screens unless the request explicitly requires it
- Do not refactor surrounding code while fixing a targeted issue

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

## Formatting & Verification

- After every code, localization, configuration, or documentation change: run the project's lint, format, and analysis commands
- Fix all reported issues before considering the change done
- Do not finish a task with failing lint, format warnings, or generated-code drift
- After changing localization or code-generation source files: regenerate output before running verification

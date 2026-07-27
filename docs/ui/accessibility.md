# Accessibility Requirements

## Baseline requirements

- All interactive controls need an accessible name.
- Landmark regions must be present and stable.
- Focus order must be predictable.
- keyboard-only operation must support the key flows.
- Dialogs, drawers, and popovers must trap focus when open.
- Tables must use semantic table markup.
- Error messages must be associated with the relevant control.
- Contrast must remain readable at the specified theme tokens.

## Page-spec obligations

Every page spec must state:

- landmark regions
- keyboard affordances
- focus movement
- accessible names
- table or chart alternatives
- error announcement strategy

## Security overlap

Accessibility artifacts must not expose secrets, tokens, raw identifiers, or internal paths.

# Component Contracts

## Contract rules

1. Generic components must stay generic.
2. Feature components may own state orchestration for one funnel concern.
3. Page components may compose feature components and route chrome only.
4. API clients may translate typed transport payloads, not business rules.
5. Calculations, entitlements, and authorization logic stay server-owned.

## Required contracts

| Component family | Contract evidence |
| --- | --- |
| Button and form controls | Typed props, states, keyboard behaviour, error handling |
| Layout primitives | Responsive behaviour and region semantics |
| Status and progress components | Loading, complete, warning, failed, stale, and empty semantics |
| Table shell | Row semantics, empty rows, loading rows, and no-data copy |
| Page header | Route title, supporting context, and action placement |
| Navigation components | Route names, current-step state, and focus order |

## Prohibited contract contents

- secret values
- provider keys
- session tokens
- internal storage paths
- unrestricted artifact ids
- authorization decisions
- financial calculations


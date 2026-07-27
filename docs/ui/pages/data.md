# Data Page Specification

## User goal

Load and inspect the current listing data for a selected project.

## Inputs

- selected project
- server response for data loading
- progress state

## Outputs

- load progress
- current selection count
- completion, warning, failed, and stale states

## Layout regions

- page header
- progress banner
- results area
- supporting copy

## Actions

- load selected listings
- retry after redacted failures
- switch to the next unlocked funnel step

## Accessibility

- announce progress changes
- keep the primary action reachable by keyboard
- preserve semantic text for summary state


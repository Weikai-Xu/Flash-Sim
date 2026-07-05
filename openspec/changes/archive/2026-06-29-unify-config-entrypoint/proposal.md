## Why

`flash_sim.config` and `flash_sim.common` both currently act as configuration entry points, which makes it unclear where flash geometry, timing, and derived hardware constants should be changed. Consolidating the configuration source now reduces drift risk while preserving the current simulator behavior and public imports.

## What Changes

- Establish `flash_sim.config` as the single authoritative configuration entry point for default geometry, timing, runtime policy, event-runtime geometry, and derived configuration constants.
- Move or expose the event-driven runtime constants currently owned by `flash_sim.common` through `flash_sim.config`, then keep `flash_sim.common` as a backward-compatible re-export surface for existing imports.
- Preserve current constant names and effective values used by the event-driven path, standalone path, trace generators, tests, and reports.
- Add regression coverage proving that importing configuration values from `flash_sim.common` produces the same values as the authoritative definitions in `flash_sim.config`.
- No **BREAKING** import or behavior changes are intended.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `default-flash-configuration`: add requirements that default and event-runtime configuration values have a single authoritative source and that legacy `flash_sim.common` configuration exports remain compatible.

## Scope

In scope:

- `flash_sim.config`: default constants, config dataclasses, event-runtime geometry helpers, and derived configuration exports.
- `flash_sim.common`: compatibility imports/re-exports for configuration constants while retaining event, request, transaction, address, and scheduling helper definitions.
- Direct consumers in `flash_sim/`, `test_script/`, and trace-generation helpers that rely on configuration constants.
- Tests that compare `config.py` authoritative values with `common.py` compatibility exports and guard existing simulator behavior.

Out of scope:

- Changing NAND geometry, timing, GC policy, scheduling behavior, address mapping semantics, or request completion semantics.
- Renaming public constants without compatibility aliases.
- Reworking event/request/transaction classes in `flash_sim.common`.
- Changing CLI arguments, trace formats, generated report schemas, or visualization output.

## Non-goals

- This change does not introduce dynamic runtime reconfiguration.
- This change does not remove `flash_sim.common` as an importable module.
- This change does not attempt a broader package layout refactor.
- This change does not fix unrelated encoding issues in comments or documentation.

## Impact

- Code impact: `flash_sim/config.py`, `flash_sim/common.py`, and possibly imports that can be narrowed to the new config entry point.
- API impact: existing public imports from `flash_sim.config` and `flash_sim.common` should continue to work.
- Test impact: add or update tests around default configuration, event-runtime constants, and legacy compatibility exports.
- Dependency impact: none.

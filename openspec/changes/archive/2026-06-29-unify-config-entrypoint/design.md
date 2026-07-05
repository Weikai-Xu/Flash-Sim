## Context

The project has two runtime paths: the standalone simulator path primarily imports structured configuration from `flash_sim.config`, while the event-driven path imports many constants and runtime helpers from `flash_sim.common`. Today `flash_sim.common` derives some values from `make_event_runtime_geometry()` but also hard-codes other configuration values, so developers cannot tell which module is the source of truth.

The change must preserve existing behavior. In particular, legacy event-runtime constants such as `SECTOR_PER_PAGE`, static-region boundaries, parallelism limits, and timing aliases must keep their current effective values even when those values are not identical to the standalone `FlashGeometry()` defaults.

## Goals / Non-Goals

**Goals:**

- Make `flash_sim.config` the only module that defines configuration defaults and derived configuration constants.
- Keep `flash_sim.common` import-compatible for existing event-driven modules, tests, trace generators, and reports.
- Avoid circular imports by keeping `flash_sim.config` independent from `flash_sim.common`.
- Add focused regression tests that lock down the compatibility surface and important derived values.

**Non-Goals:**

- Do not change NAND geometry, timing, scheduling, GC, request splitting, trace format, CLI behavior, or report schemas.
- Do not remove or rename existing `flash_sim.common` exports.
- Do not move event/request/transaction classes out of `flash_sim.common`.
- Do not normalize legacy constants whose current values are already part of runtime behavior.

## Decisions

### Decision: `flash_sim.config` owns configuration values; `flash_sim.common` re-exports them

Add authoritative module-level exports to `flash_sim.config` for the event-runtime constants currently defined in `flash_sim.common`. Update `flash_sim.common` to import those names explicitly and expose them under the same public names.

Alternative considered: move all of `flash_sim.common` into `flash_sim.config`. That would mix event types, request classes, time-provider hooks, and configuration in one larger module, making the package boundary less clear.

Alternative considered: leave both modules as independent config entry points. That preserves the current ambiguity and leaves future changes vulnerable to value drift.

### Decision: Preserve legacy event-runtime values as explicit config semantics

Where constants are derived from runtime geometry, compute them in `flash_sim.config` from `make_event_runtime_geometry()` or a shared event-runtime geometry instance. Where a legacy value is intentionally independent, such as event-path sector granularity, define that value explicitly in `flash_sim.config` and use it when computing derived constants such as `STATIC_BASE_LHA`.

Alternative considered: force all constants to use `FlashGeometry` field values. That would make the model look cleaner but could change request splitting, static-region address bounds, generated traces, or preconditioning payload sizes.

### Decision: Keep compatibility aliases boring and explicit

Use explicit imports in `flash_sim.common` rather than wildcard imports or dynamic forwarding. This keeps the compatibility surface readable and makes missing exports fail during import or tests.

Alternative considered: expose a dynamic `__getattr__` compatibility layer. That would reduce repeated names but make static analysis, grep, and refactoring harder.

### Decision: Test the contract from both sides

Add tests that import the same configuration constants from `flash_sim.config` and `flash_sim.common`, then compare values for equality. Add a derived-value test for static-region calculations and event-runtime geometry-backed constants.

Alternative considered: rely on existing runtime integration tests. Those tests may catch large regressions but would not identify the configuration boundary as the source of failure.

## Design Rationale

This design separates two concerns that are currently intertwined. `flash_sim.config` becomes the configuration entry point because it already contains the structured dataclasses, constructors, serializers, default constants, and event-runtime helper. `flash_sim.common` remains the event-domain module because it already contains request/event enums, data classes, simulation hooks, and logging helpers.

The compatibility layer is deliberately conservative. Existing code can keep importing constants from `flash_sim.common`, while new code can import from `flash_sim.config` when it needs configuration values. This creates one source of truth without forcing a broad import migration in the same change.

## Risks / Trade-offs

- [Risk] A constant is missed during the move and a legacy import breaks. -> Mitigation: enumerate current configuration exports in tests and import them from both modules.
- [Risk] A derived value changes because it is recomputed from a different base. -> Mitigation: snapshot critical event-runtime values and formulas, especially `PAGE_PER_BLOCK`, `SECTOR_PER_PAGE`, bank counts, and `STATIC_BASE_LHA`.
- [Risk] Circular imports appear if `config.py` imports event-domain types. -> Mitigation: keep `config.py` independent from `common.py`; only `common.py` imports configuration aliases.
- [Risk] Cleanup expands into unrelated refactoring. -> Mitigation: do not move event/request/transaction classes or change runtime algorithms in this change.

## Migration Plan

1. Add authoritative event-runtime configuration constants and derived values to `flash_sim.config`.
2. Replace the hard-coded configuration block in `flash_sim.common` with explicit compatibility imports from `flash_sim.config`.
3. Optionally narrow direct imports in nearby modules when they clearly need configuration-only values, without requiring a full repository import rewrite.
4. Add regression tests for config/common value parity and critical derived values.
5. Run the focused config tests and relevant event-runtime tests.

Rollback is straightforward: restore the previous `flash_sim.common` configuration constant block and remove the new config exports. No data migration is involved.

## Open Questions

- Should a future change formally deprecate importing configuration values from `flash_sim.common`? This change keeps those imports supported and does not emit warnings.

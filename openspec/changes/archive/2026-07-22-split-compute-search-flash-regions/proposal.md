## Why

Current flash geometry reserves one static address area and one static chip region for `SEARCH`, `COMPUTE`, and `STATIC_WRITE`. This makes search and compute traffic share the same chip-level address domain even though the model now needs to reason about them as separate physical regions.

## What Changes

- Split the existing static address domain into distinct compute and search regions at chip granularity.
- Add geometry-derived base addresses that mark the start of the compute region and the search region, while preserving the random-access base boundary.
- Route `COMPUTE` requests only through the compute address range and compute-dedicated static chips.
- Route `SEARCH` requests only through the search address range and search-dedicated static chips.
- Keep `STATIC_WRITE` scoped to the static/CIM address space, with request-type validation preventing accidental cross-region access.
- Update trace-generation helpers and tests to target the new base addresses instead of assuming one shared static base.
- **BREAKING**: Existing traces that place both `SEARCH` and `COMPUTE` at the old shared `STATIC_BASE_LHA` may need their CIM request addresses updated.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `default-flash-configuration`: Add geometry-derived compute/search chip-region sizing and base-address values.
- `host-device-request-flow`: Validate `SEARCH`, `COMPUTE`, and `STATIC_WRITE` against their intended address domains before data fetch or FTL submission.
- `ftl-scheduling-and-media-model`: Map compute and search transactions to separate static chip ranges and schedule them only on matching chips.
- `trace-test-data-generation`: Generate legal search and compute addresses from their distinct region bases.

## Non-goals

- Do not change SEARCH or COMPUTE timing, payload-size formulas, or parallel wave semantics.
- Do not implement functional CAM/GEMV value computation.
- Do not change ordinary random-access `READ`/`WRITE` address translation, GC, static wear-leveling, or preconditioning behavior except where they need the updated non-CIM chip count.
- Do not add a new external trace format beyond the existing address-field semantics.

## Impact

In scope are `flash_sim/config.py`, `flash_sim/common.py`, `flash_sim/HIL.py`, `flash_sim/FTL.py`, trace parser/generator helpers that expose static base constants, and focused regression tests under `test_script/`.

Out of scope are `flash_sim/PHY.py` transfer timing internals, page-data validity checks for ordinary reads, validation result artifacts, and unrelated simulator reporting changes.

Test coverage should include geometry/base-address derivation, request-domain rejection for cross-region search/compute requests, FTL address mapping to separate chip ranges, and generated trace commands using the new compute/search ranges.

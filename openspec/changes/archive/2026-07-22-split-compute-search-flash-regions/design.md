## Context

The event-driven runtime currently derives `STATIC_BASE_LHA` from random-access capacity and treats the remaining per-channel static chips as one combined CIM/static-write address space. `HIL.segment(...)` calls `FTL.get_static_address(...)` for `SEARCH`, `COMPUTE`, and `STATIC_WRITE`, and `FTL.get_static_address(...)` maps all of those LHAs onto the last `STATIC_CHIP_PER_CHANNEL` chips in each channel.

The new model needs compute and search regions to be physically distinguishable at chip granularity. The implementation must keep the existing compact runtime geometry style, because many tests and helpers import constants from `flash_sim.common`.

## Goals / Non-Goals

**Goals:**

- Represent random-access, compute, search, and remaining static-write domains with deterministic geometry-derived base addresses.
- Preserve chip-granular address partitioning: each CIM region owns whole chips per channel.
- Validate request address domains by request type before host data fetch or FTL submission.
- Keep address translation and scheduling deterministic under runtime geometry overrides.
- Update tests and trace generation to use the new base constants.

**Non-Goals:**

- No change to ONFI timing, PHY payload formulas, SEARCH wave rules, or COMPUTE selected-WL rules.
- No change to random-access LPA placement beyond excluding all reserved CIM/static chips.
- No new external trace schema.

## Decisions

1. Add explicit per-channel reserved chip counts for compute and search.

   `FlashGeometry` will expose `compute_chip_per_channel` and `search_chip_per_channel`, defaulting to the current one reserved static chip split as `compute=1`, `search=0` only if backward compatibility is required by old configs. For the new behavior, event-runtime defaults should reserve at least one compute chip and one search chip, so `chip_per_channel` must be large enough to leave random-access chips.

   Alternative considered: split one existing static chip internally by die or plane. That would not satisfy the requested chip-granular partitioning and would keep TSU chip queues shared.

2. Derive base addresses in order from random capacity, then compute capacity, then search capacity.

   The address layout is:

   - `[0, COMPUTE_BASE_LHA)` random-access data
   - `[COMPUTE_BASE_LHA, SEARCH_BASE_LHA)` compute region
   - `[SEARCH_BASE_LHA, STATIC_BASE_LHA)` search region
   - `[STATIC_BASE_LHA, STATIC_END_LHA)` static-write region, if configured

   `COMPUTE_BASE_LHA` replaces the old meaning of "first non-random LHA"; `STATIC_BASE_LHA` remains available as the base for non-CIM static writes. This keeps every base address a region start instead of overloading one name for all static traffic.

   Alternative considered: keep `STATIC_BASE_LHA` as the first CIM address and add offsets. That would leave callers without an explicit search base and would make request validation less readable.

3. Make region-aware address translation take a request type.

   `FTL.get_static_address(...)` will either become region-aware or delegate to a helper that accepts the request type/domain. HIL should pass the request type so compute LHAs are normalized against `COMPUTE_BASE_LHA`, search LHAs against `SEARCH_BASE_LHA`, and static writes against `STATIC_BASE_LHA`.

   Alternative considered: infer the region only from the raw LHA. That works for validation, but passing the request type gives clearer errors and avoids accidental cross-region routing when an address lies in another legal region.

4. Keep TSU chip classification derived from physical chip ranges.

   Static/CIM chip predicates should distinguish compute, search, and static-write chip ranges. `try_activate(...)` can continue using per-chip queues and the current priority methods, but a compute-only chip should not run search transactions and a search-only chip should not run compute transactions.

## Design Rationale

The existing runtime already treats chip as the scheduling isolation unit, so carrying that idea into the address model is the least disruptive design. Geometry-derived base addresses keep trace fixtures deterministic and make invalid cross-region requests fail at the HIL boundary, before they can create host data messages or queue transactions on the wrong chip.

Using separate base constants also makes the simulator easier to configure for experiments: capacity changes and chip-count changes flow from one `FlashGeometry` object into `common.configure_event_runtime(...)`, HIL validation, FTL mapping, and trace generation.

## Risks / Trade-offs

- Existing traces may use `STATIC_BASE_LHA` for compute/search → Update fixtures and keep error messages explicit so failures point to the new bases.
- Old configs may not reserve enough chips for all regions → Validate chip counts during `FlashGeometry.__post_init__` with a clear error.
- Imported module constants can drift after runtime overrides → Refresh all derived base/end constants in `configure_event_runtime(...)` and add focused tests for override propagation.
- `STATIC_BASE_LHA` name changes practical meaning from "CIM start" to "static-write start" → Tests and docs must use `COMPUTE_BASE_LHA`/`SEARCH_BASE_LHA` for CIM requests.

## Migration Plan

1. Add geometry fields, derived capacities, and base/end properties.
2. Refresh `flash_sim.common` constants from those properties.
3. Update HIL validation and segmentation to use request-type-specific regions.
4. Update FTL static address mapping and chip classification.
5. Update trace fixtures/generators and focused tests.

Rollback is straightforward: revert the change and regenerate any traces that were moved to new region bases.

## Open Questions

- Resolved: the default event-runtime geometry keeps the previous three random-access chips per channel and increases `chip_per_channel` to reserve one compute chip, one search chip, and one static-write chip.

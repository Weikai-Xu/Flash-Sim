## ADDED Requirements

### Requirement: Configuration values have one authoritative module
The repository SHALL define default flash configuration values, event-runtime geometry defaults, timing aliases, parallelism limits, and derived hardware configuration constants in `flash_sim.config`. `flash_sim.common` MUST NOT define independent hard-coded configuration values for the same public constants; it MUST expose compatibility aliases that resolve to the authoritative values from `flash_sim.config`.

#### Scenario: Configuration constants are importable from the authoritative entry point
- **WHEN** a caller imports event-runtime configuration constants such as `CHANNEL_NO`, `CHIP_PER_CHANNEL`, `DIE_PER_CHIP`, `PLANE_PER_DIE`, `BLOCK_PER_PLANE`, `PAGE_PER_BLOCK`, `SECTOR_PER_PAGE`, `STATIC_CHIP_PER_CHANNEL`, and `STATIC_BASE_LHA` from `flash_sim.config`
- **THEN** the imports MUST succeed and provide the values used by the event-driven simulator path

#### Scenario: Common compatibility exports match the authoritative values
- **WHEN** a caller imports the same configuration constant names from both `flash_sim.config` and `flash_sim.common`
- **THEN** every value exposed through `flash_sim.common` MUST equal the authoritative value exposed through `flash_sim.config`

### Requirement: Event-runtime derived constants preserve existing behavior
The event-runtime configuration exported by `flash_sim.config` SHALL preserve the current effective values used by the event-driven simulator path, including legacy values that are intentionally separate from standalone `FlashGeometry()` defaults. Derived constants such as page count, bank count, and static-region base address MUST be computed from the event-runtime configuration values rather than duplicated independently in `flash_sim.common`.

#### Scenario: Event-runtime geometry-backed constants remain aligned
- **WHEN** a caller compares `PAGE_PER_BLOCK`, `BLOCK_PER_PLANE`, `PLANE_PER_DIE`, `DIE_PER_CHIP`, `CHANNEL_NO`, and `CHIP_PER_CHANNEL` with the corresponding values from `make_event_runtime_geometry()`
- **THEN** those constants MUST match the event-runtime geometry values

#### Scenario: Static-region base address uses authoritative event-runtime values
- **WHEN** a caller computes `SECTOR_PER_PAGE * PAGE_PER_BLOCK * BLOCK_PER_PLANE * PLANE_PER_DIE * DIE_PER_CHIP * CHANNEL_NO * (CHIP_PER_CHANNEL - STATIC_CHIP_PER_CHANNEL)` using values imported from `flash_sim.config`
- **THEN** the result MUST equal `STATIC_BASE_LHA`

#### Scenario: Legacy sector granularity remains available through common
- **WHEN** a caller imports `SECTOR_PER_PAGE` from `flash_sim.common`
- **THEN** the value MUST match `flash_sim.config.SECTOR_PER_PAGE` and continue to represent the event-driven request payload granularity

### Requirement: Existing structured configuration APIs remain unchanged
The consolidation SHALL NOT change the behavior of `FlashGeometry`, `FlashConfig`, `TimingConfig`, `OnfiTimingConfig`, `ParallelConfig`, `RuntimeConfig`, or `make_event_runtime_geometry()` except for exposing additional authoritative constants from `flash_sim.config`.

#### Scenario: Default structured configuration remains stable
- **WHEN** a caller constructs `FlashGeometry()`, `FlashConfig()`, and `FlashConfig.from_dict({})`
- **THEN** their default geometry, timing, parallelism, and runtime policy values MUST remain consistent with the existing default-flash-configuration requirements

#### Scenario: Existing common event-domain imports remain stable
- **WHEN** a caller imports event/request classes and helpers such as `EventType`, `MessageType`, `Request`, `Transaction`, `SimEvent`, `CURRENT_TIME`, and `Register_event` from `flash_sim.common`
- **THEN** those imports MUST continue to work without requiring callers to import from `flash_sim.config`

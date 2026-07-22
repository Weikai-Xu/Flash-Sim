# default-flash-configuration Specification

## Purpose
TBD - created by archiving change fix-pytest-regressions. Update Purpose after archive.
## Requirements
### Requirement: Default flash geometry baseline is consistent
The repository SHALL expose a single default geometry baseline for direct `FlashGeometry()` construction and for the default `FlashConfig().geometry` path. That baseline MUST match the documented 3D NAND configuration of `layers_per_block=128`, `sub_blocks_per_block=4`, `blocks_per_plane=1024`, `planes_per_die=4`, and `dies=4`.

#### Scenario: Direct geometry construction uses documented defaults
- **WHEN** a caller instantiates `FlashGeometry()` without overrides
- **THEN** the resulting object MUST report `layers_per_block=128`, `sub_blocks_per_block=4`, `blocks_per_plane=1024`, `planes_per_die=4`, and `dies=4`

#### Scenario: Default FlashConfig exposes the same geometry baseline
- **WHEN** a caller instantiates `FlashConfig()` without overrides
- **THEN** `FlashConfig().geometry` MUST expose the same default geometry values as a direct `FlashGeometry()` construction

### Requirement: Default configuration constructors and serializers stay aligned
`FlashConfig.from_dict({})`, `FlashConfig.to_dict()`, and geometry-facing tooling SHALL use the same default flash baseline as direct constructors, and MUST NOT silently substitute a different debugging geometry. `FlashConfig` SHALL also expose event-driven runtime policy knobs for GC and write-backpressure behavior.

#### Scenario: Empty configuration input preserves the shared defaults
- **WHEN** a caller builds a config with `FlashConfig.from_dict({})`
- **THEN** the resulting geometry MUST match the default baseline used by `FlashConfig()` and `FlashGeometry()`

#### Scenario: Default config round-trip preserves geometry defaults
- **WHEN** a caller serializes `FlashConfig()` with `to_dict()` and reconstructs it with `from_dict(...)`
- **THEN** the reconstructed geometry MUST match the original default geometry values exactly

#### Scenario: Runtime GC/write-path policy has stable defaults
- **WHEN** a caller instantiates `FlashConfig()` without overrides
- **THEN** the runtime config MUST expose `gc_low_watermark=3`, `stop_servicing_writes_threshold=1`, `gc_victim_policy="greedy"`, `static_wl_wear_gap_threshold=2`, and `write_allocation_mode="lpa-affine"`

#### Scenario: Runtime config round-trip preserves policy knobs
- **WHEN** a caller supplies runtime config values through `FlashConfig.from_dict(...)` and then serializes with `to_dict()`
- **THEN** the serialized `runtime` object MUST preserve `gc_low_watermark`, `stop_servicing_writes_threshold`, `gc_victim_policy`, `static_wl_wear_gap_threshold`, and `write_allocation_mode`

#### Scenario: Unsupported GC victim policy fails explicitly
- **WHEN** a caller configures `gc_victim_policy` to a value other than `"greedy"`
- **THEN** config construction MUST fail explicitly instead of silently falling back to a different GC policy

### Requirement: Geometry exposes distinct compute and search address regions

`FlashGeometry` SHALL expose deterministic LHA base and end values for random-access, compute, search, and static-write regions. The region boundaries MUST be derived from chip-granular per-channel reservations and MUST be exported through the event-runtime constants refreshed by `configure_event_runtime(...)`.

#### Scenario: Default runtime bases are ordered

- **WHEN** the default event-runtime geometry is loaded
- **THEN** `COMPUTE_BASE_LHA` MUST equal the end of the random-access region, `SEARCH_BASE_LHA` MUST equal the end of the compute region, and `STATIC_BASE_LHA` MUST equal the end of the search region

#### Scenario: Region capacity follows chip reservations

- **WHEN** a geometry configures different `compute_chip_per_channel`, `search_chip_per_channel`, or `static_chip_per_channel` values
- **THEN** the compute, search, and static-write region lengths MUST change by whole-chip capacities while preserving their base-address ordering

#### Scenario: Runtime override refreshes region constants

- **WHEN** `Engine(config=...)` applies a geometry override that changes CIM/static chip reservations
- **THEN** imported runtime modules MUST observe updated compute/search/static base and end constants from the same geometry

### Requirement: CIM/static chip reservations are validated and round-trippable

`FlashConfig.from_dict(...)` and `FlashConfig.to_dict()` SHALL preserve compute, search, and static-write chip reservation fields. Geometry construction MUST reject negative reservations and MUST reject configurations that leave no random-access chip per channel.

#### Scenario: CIM chip reservations round-trip

- **WHEN** a caller supplies `compute_chip_per_channel`, `search_chip_per_channel`, and `static_chip_per_channel` in `geometry`
- **THEN** serializing and reconstructing the config MUST preserve those values exactly

#### Scenario: Invalid chip reservations fail explicitly

- **WHEN** a caller configures negative region chip counts or reserves all chips for compute/search/static-write regions
- **THEN** config construction MUST raise a `ValueError` with a reservation-related message

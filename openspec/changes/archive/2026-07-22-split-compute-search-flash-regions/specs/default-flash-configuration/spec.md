## ADDED Requirements

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

## 1. Geometry And Runtime Constants

- [x] 1.1 Modify `flash_sim/config.py` `FlashGeometry` to add compute/search chip reservation fields, derived region capacities, and compute/search/static base/end properties.
- [x] 1.2 Modify `FlashConfig.from_dict(...)` and `FlashConfig.to_dict()` in `flash_sim/config.py` to parse and serialize the new reservation fields.
- [x] 1.3 Modify `flash_sim/common.py` `configure_event_runtime(...)` and module constants to export `COMPUTE_BASE_LHA`, `SEARCH_BASE_LHA`, `STATIC_BASE_LHA`, and region end constants from `FlashGeometry`.
- [x] 1.4 Modify runtime propagation in `flash_sim/engine.py` to refresh the new region constants in already-imported modules.

## 2. Request Validation And Address Mapping

- [x] 2.1 Modify `flash_sim/HIL.py` region helpers and `_validate_request_domain(...)` so `COMPUTE`, `SEARCH`, `STATIC_WRITE`, and ordinary `WRITE` validate against distinct legal ranges.
- [x] 2.2 Modify `flash_sim/HIL.py` `segment(...)` to pass request type/domain information when computing static/CIM physical addresses.
- [x] 2.3 Modify `flash_sim/FTL.py` `FTL.get_static_address(...)` or add equivalent helpers so compute/search/static-write LHAs normalize against their own base address and map to their own chip ranges.
- [x] 2.4 Modify TSU chip classification in `flash_sim/FTL.py` so compute chips only dispatch compute transactions, search chips only dispatch search transactions, and static-write chips only dispatch static-write transactions.

## 3. Trace Helpers And Fixtures

- [x] 3.1 Modify `test_script/generate_test_trace.py` to generate compute and search commands from their distinct region bases.
- [x] 3.2 Modify `test_script/request_resource_contention_experiments.py` static/CIM helper functions to use request-type-specific capacity and base constants.
- [x] 3.3 Update CIM parallel trace fixtures under `test_case/cim_parallel/` so compute and search requests use legal separated regions.

## 4. Tests And Verification

- [x] 4.1 Add or update `test_script/test_config.py` coverage for region base ordering, chip-reservation validation, runtime constant propagation, and config round-trip.
- [x] 4.2 Add or update request-domain tests in `test_script/test_request_error_handling.py` for cross-region compute/search rejection and legal base acceptance.
- [x] 4.3 Add or update FTL mapping tests verifying compute and search addresses land on separate chip ranges.
- [x] 4.4 Run focused pytest coverage for config, request validation, trace generation, and CIM parallel traces.

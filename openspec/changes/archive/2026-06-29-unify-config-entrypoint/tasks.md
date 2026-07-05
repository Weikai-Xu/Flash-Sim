## 1. Audit Current Configuration Surface

- [x] 1.1 Audit `flash_sim/common.py` and list the configuration constants to move or alias from `flash_sim.config`, including geometry, parallelism, timing, ONFI, static-region, and power/timing threshold values.
- [x] 1.2 Audit direct consumers in `flash_sim/`, `test_script/`, and trace-generation helpers to identify imports that must keep working from `flash_sim.common`.

## 2. Config Module Implementation

- [x] 2.1 Modify `flash_sim/config.py` to add authoritative event-runtime configuration exports, including `CHANNEL_NO`, `CHIP_PER_CHANNEL`, `DIE_PER_CHIP`, `PLANE_PER_DIE`, `BLOCK_PER_PLANE`, `SL_PER_BLOCK`, `SSL_PER_SL`, `PAGE_PER_BLOCK`, `SECTOR_PER_PAGE`, `COMPUTE_MAX_PARALLEL_SL`, `SEARCH_MAX_PARALLEL_WL`, `PAGE_NO_PER_SEARCH_BANK`, `PAGE_NO_PER_COMPUTE_BANK`, `COMPUTE_BANK_PER_PLANE`, `SEARCH_BANK_PER_PLANE`, `STATIC_CHIP_PER_CHANNEL`, and `STATIC_BASE_LHA`.
- [x] 2.2 Modify `flash_sim/config.py` to add authoritative timing and interface aliases currently exposed by `flash_sim.common`, including `DEFAULT_ONFI_TIMING`, `ONFI_CHANNEL_WIDTH_BYTES`, `T_READ_LSB`, `T_PROG`, `T_BERS`, `T_SEARCH`, and `T_COMPUTE`.
- [x] 2.3 Modify `flash_sim/config.py` to keep legacy event-runtime values explicit where they differ from standalone `FlashGeometry()` defaults, without changing `FlashGeometry`, `FlashConfig`, `RuntimeConfig`, or `make_event_runtime_geometry()` behavior unless required for compatibility.

## 3. Common Module Compatibility

- [x] 3.1 Modify `flash_sim/common.py` to delete the independent hard-coded configuration assignments that duplicate values now owned by `flash_sim.config`.
- [x] 3.2 Modify `flash_sim/common.py` to explicitly import and re-export the authoritative configuration constants from `flash_sim.config` under the existing public names.
- [x] 3.3 Keep `flash_sim/common.py` event-domain definitions unchanged, including `EventType`, `MessageType`, `RequestType`, `TransactionType`, `Request`, `Transaction`, `FlashAddress`, `SimEvent`, `CURRENT_TIME`, and `Register_event`.

## 4. Verification Tests

- [x] 4.1 Add or update `test_script/test_config.py` to verify every moved configuration constant is importable from `flash_sim.config`.
- [x] 4.2 Add or update tests to verify `flash_sim.common` compatibility exports equal the corresponding authoritative values from `flash_sim.config`.
- [x] 4.3 Add or update tests to verify event-runtime derived values, including `PAGE_PER_BLOCK`, bank counts, and `STATIC_BASE_LHA`, are computed from the authoritative constants.
- [x] 4.4 Add or update tests to verify representative event-domain imports from `flash_sim.common` still work after the compatibility import change.

## 5. Test Execution

- [x] 5.1 Run the focused configuration tests, including `python -m pytest test_script/test_config.py`.
- [x] 5.2 Run relevant event-driven compatibility tests that use `flash_sim.common` constants, such as static WL, preconditioning, trace generation, and request-resource contention tests.
- [x] 5.3 Run the broader test suite if focused tests pass and runtime cost is acceptable.

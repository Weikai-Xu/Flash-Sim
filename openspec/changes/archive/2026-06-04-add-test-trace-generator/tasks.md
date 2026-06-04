## 1. Rename Test Script Root

- [x] 1.1 Rename the repository test directory from `tests/` to `test_script/`, preserve package markers such as `__init__.py`, and update any moved files whose path logic or imports assume the old `tests/` location.
- [x] 1.2 Modify `pyproject.toml` `[tool.pytest.ini_options].testpaths`, update README or other repository text that hard-codes `tests/`, and keep pytest discovery pointed at `test_script/`.

## 2. Add Generator Runtime Fixture And Address Pool Helpers

- [x] 2.1 Add a new generator module under `test_script/` (for example `test_script/generate_test_trace.py`) that constructs the minimal `Block_Manager` / `PHY` / `Address_Mapping_Unit` fixture, runs `flash_sim/FTL.py::Block_Manager.preconditioning`, and snapshots the post-preconditioning plane state needed for trace generation.
- [x] 2.2 In the new generator module, add helper functions that derive precondition-backed read candidates from `pre_data/precondition_data.json`, compute legal random-access write candidates that stay below the AMU mapping-reserved tail, and compute legal static-area `search` / `compute` address candidates from `flash_sim/common.py`.

## 3. Implement Trace Assembly

- [x] 3.1 In `test_script/generate_test_trace.py`, implement request-recipe builders for precondition-backed `read`, dependent `write -> read` pairs, and at least one `search` plus one `compute`, then serialize the final engine trace JSON to `test_case/test_trace.json` by default.
- [x] 3.2 In `test_script/generate_test_trace.py`, implement target-plane selection and GC-pressure estimation using post-preconditioning `PlaneBKE` state plus `GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD`, including the fallback that creates invalid pages with overwrite writes when no suitable victim-ready plane already exists.
- [x] 3.3 In `test_script/generate_test_trace.py`, implement the seeded constrained scheduler that preserves dependency order while preferring a different request type whenever multiple dependency-free families are available.
- [x] 3.4 In `test_script/generate_test_trace.py`, add the CLI entry behavior for `--seed`, `--output`, `--pre-data`, and the chosen request-budget parameter, and print a short summary of the generated trace and selected GC target.

## 4. Verification

- [x] 4.1 Add focused tests under `test_script/` for the new generator module, covering deterministic output for a fixed seed, presence of all four primary request types, legality of random-access versus static address ranges, and existence of both precondition-backed reads and write-readback pairs.
- [x] 4.2 Add an integration-style regression under `test_script/` that validates the generated trace carries enough target-plane writes to satisfy the GC-pressure calculation against the live post-preconditioning state, rather than only matching a hard-coded write count.
- [x] 4.3 Run the relevant pytest command against `test_script/` and run the new generator script once to confirm `test_case/test_trace.json` is produced successfully from the repository root.

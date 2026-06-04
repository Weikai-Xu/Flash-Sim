## Why

Running `flash_sim/main.py` with the generated `test_case/test_trace.json` currently crashes when `PHY` resumes a suspended write command. The resume path inspects a `TransactionType` enum as if it were an iterable string and also uses an event payload shape that differs from the rest of the `PHY` event flow, making suspend/resume behavior fragile exactly when mixed read/write/GC traffic is present.

## What Changes

- Fix `PHY._send_resume_command(...)` so resumed write commands classify GC vs non-GC writes using the same transaction-type handling as the normal write path.
- Normalize resume-generated completion events to use the same parameter structure as other `PHY` events so resumed commands can be executed by `PHY.execute(...)` without special cases.
- Invalidate stale pre-suspend completion events so a suspended write or erase cannot complete twice after being resumed.
- Add regression coverage for a suspended write or erase command resuming after an interleaved high-priority request, with `test_case/test_trace.json` as an end-to-end validation target.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ftl-scheduling-and-media-model`: clarify that suspended `PHY` write and erase commands must resume through the normal event pipeline without crashing, and that resumed GC writes must preserve GC-aware chip status classification.

## Non-goals

- No changes to trace generation logic, request mix generation, or `test_case/test_trace.json` contents.
- No changes to TSU scheduling policy, GC trigger thresholds, or AMU mapping semantics beyond what is needed to let existing suspend/resume behavior complete safely.
- No broad refactor of `PHY` storage execution outside the suspend/resume path.

## Impact

- In scope modules/functions: `flash_sim/PHY.py`, especially `DieBKE.prepare_suspend(...)`, `PHY._send_resume_command(...)`, related resume-event handling in `PHY.execute(...)`, event registration helpers in `flash_sim/common.py` and `flash_sim/engine.py`, and targeted regression tests under `test_script/`.
- Out of scope modules/functions: trace generator scripts in `test_script/generate_test_trace.py`, host request construction, and block manager preconditioning logic.
- Primary test target: a regression that reproduces a suspended write resume after an interleaved read, plus an end-to-end run of `flash_sim/main.py` with `test_case/test_trace.json` to confirm the simulator no longer aborts at resume time.

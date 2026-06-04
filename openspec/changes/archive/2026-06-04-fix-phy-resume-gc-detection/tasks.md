## 1. Resume Path Fix

- [x] 1.1 Modify `flash_sim/PHY.py` `PHY._send_resume_command(...)` to classify resumed GC writes using normalized transaction-type metadata instead of probing the `TransactionType` enum directly.
- [x] 1.2 Modify `flash_sim/PHY.py` `PHY._send_resume_command(...)` to register resumed write and erase completion events with the same dict payload shape used elsewhere in `PHY.execute(...)`.
- [x] 1.3 Modify `flash_sim/PHY.py` `DieBKE.prepare_suspend(...)` plus event registration helpers in `flash_sim/common.py` and `flash_sim/engine.py` so superseded write/erase completion events can be marked ignored before resume schedules replacement events.

## 2. Regression Coverage

- [x] 2.1 Add or update a focused regression under `test_script/` that exercises resumed write or erase scheduling and verifies chip status plus completion-event payload content.
- [x] 2.2 Verify the fix by running a targeted test command and an end-to-end `flash_sim/main.py` run against `test_case/test_trace.json`, then record the completed state in this change.

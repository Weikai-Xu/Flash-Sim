## 1. Request And Report Data Model

- [x] 1.1 Modify `flash_sim/common.py::Request` and any related request/transaction metadata to add stable trace-scoped request identifiers and the fields needed by request-level latency attribution.
- [x] 1.2 Add `flash_sim/request_latency_report.py` with the recorder / aggregator types that collect stage intervals, merge breakdown durations, reconcile overlap or untracked time, and serialize the final JSON payload.

## 2. Instrument The Request Path

- [x] 2.1 Modify `flash_sim/Host.py`, `flash_sim/pcie_link.py`, and `flash_sim/HIL.py` to record Host SQ wait, request dispatch, PCIe send/receive, request completion, and cache-ack timing boundaries needed by the reporting module.
- [x] 2.2 Modify `flash_sim/FTL.py` to expose AMU mapping-wait intervals, TSU queue-entry to first-dispatch timing, and any request/transaction hooks needed for reporting without changing the scheduling policy.
- [x] 2.3 Modify `flash_sim/HIL.py::Data_Cache` / `Cache_Manager` and any flush-generated transaction metadata so buffered `WRITE` / `STATIC_WRITE` requests preserve origin lineage through cache overwrite and backend flush.
- [x] 2.4 Modify `flash_sim/PHY.py` to emit request-attributable command-transfer, data-in, array-execution, and data-out timing intervals for all relevant transaction types.

## 3. Finalize And Export Reports

- [x] 3.1 Modify `flash_sim/engine.py::Initialize_event_queue`, `Run`, and `Start_simulation` to attach the latency recorder, preserve trace file context, perform the final cache drain pass, and trigger report export after the event queue is truly exhausted.
- [x] 3.2 Modify `flash_sim/main.py` and any event-driven entry helpers to route request-level report files into `report/<trace-stem>_request_latency.json` while preserving existing `output/*.log` behavior.

## 4. Verification

- [x] 4.1 Add focused tests under `tests/` for the new report aggregator module, including breakdown reconciliation, zero-valued skipped stages, and buffered-write persistence status handling.
- [x] 4.2 Add or update end-to-end event-driven tests under `tests/` to verify that generated report JSON captures PCIe, mapping-wait, TSU, and PHY phases for representative read and write traces.
- [x] 4.3 Run the relevant automated test commands for the touched request-flow, FTL, PHY, and report-export paths, and confirm the generated JSON reports are machine-readable and stable enough for assertions.

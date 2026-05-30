## 1. Request Model Simplification

- [x] 1.1 Modify `flash_sim/common.py::Request` and `flash_sim/engine.py::Initialize_event_queue` to remove `data_address` / `data_size` from the event-driven request flow.
- [x] 1.2 Modify `flash_sim/Host.py::Memory.read` and `flash_sim/Host.py::Memory.get_req_data` so synthetic payload generation depends on `req.size` only.

## 2. Parser And Trace Inputs

- [x] 2.1 Modify `flash_sim/parser.py` to stop documenting or requiring `data_address` / `data_size` for `write`, `static_write`, `search`, and `compute`.
- [x] 2.2 Modify `flash_sim/trace_generation/gen_gc_test.py` and any directly related in-repo sample traces to stop emitting the removed fields.

## 3. Verification

- [x] 3.1 Run targeted verification for parser acceptance of size-only traces and for event-driven request initialization without `data_address` / `data_size`.

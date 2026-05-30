## Why

The simulator no longer models real host-side data buffers, but `Request` and trace inputs still carry `data_address` and `data_size` as if payload DMA were being simulated. That duplication makes traces noisier, keeps dead fields alive in the core request model, and conflicts with the planned direction where request size alone defines the amount of placeholder data the simulator needs.

## What Changes

- **BREAKING** Remove `data_address` and `data_size` from the event-driven `Request` model in `flash_sim/common.py`.
- Update `flash_sim/engine.py` so parsed commands no longer populate removed request fields.
- Update `flash_sim/Host.py` so synthetic request payloads are generated from `Request.size` instead of host-memory pointer metadata.
- Update `flash_sim/parser.py` and in-repo trace generation inputs so `write` / `static_write` / `search` / `compute` traces no longer depend on `data_address` or `data_size`.
- Add a targeted regression check for the key behavior change: commands without `data_address` / `data_size` still parse and produce request payloads sized from `size`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `host-device-request-flow`: write-like requests fetch placeholder data by request length only, without host memory pointer fields on `Request`.
- `simulator-tooling`: trace parsing no longer requires `data_address` / `data_size`, and `size` is the only payload-length input for data-carrying commands.

## Non-goals

- Reworking how `HIL` tiles payload data into transactions.
- Introducing real host-memory contents or DMA modeling.
- Changing completion semantics for read, write, search, compute, or static-write requests beyond removing the obsolete request fields.

## Impact

- In scope modules/functions: `flash_sim/common.py::Request`, `flash_sim/engine.py::Initialize_event_queue`, `flash_sim/Host.py::Memory.get_req_data`, `flash_sim/parser.py`, and `flash_sim/trace_generation/gen_gc_test.py`.
- Supporting repository inputs may be updated where they still document the removed fields, but FTL/PHY execution logic is otherwise unchanged.
- Out of scope: controller cache semantics, FTL address translation, NAND timing, and host-side completion queue behavior.

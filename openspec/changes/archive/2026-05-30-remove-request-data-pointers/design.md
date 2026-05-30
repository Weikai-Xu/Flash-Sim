## Context

The current event-driven simulator already treats host data as synthetic placeholder values. `Host.Memory.read()` ignores the supplied address and returns repeated dummy values, while `Request.data_size` mirrors `Request.size` in the intended trace format. Despite that, `Request` still stores `data_address` and `data_size`, `Engine.Initialize_event_queue()` still copies them from parsed commands, and `parser.py` still documents them as part of the accepted command schema.

This change is small in code volume but cross-cutting across the request model, trace parsing, and host-side payload generation. Capturing the intended simplification in one place reduces the chance of leaving half-removed fields behind.

## Goals / Non-Goals

**Goals:**
- Remove obsolete host-data pointer fields from the core `Request` dataclass.
- Make request payload generation depend on `Request.size` only.
- Stop requiring `data_address` / `data_size` in the parser-facing trace schema.
- Keep write/search/compute/static-write execution behavior unchanged apart from the removed metadata.

**Non-Goals:**
- Modeling real host memory contents.
- Refactoring unrelated PCIe, HIL, FTL, or cache logic.
- Enforcing strict rejection of every legacy trace field beyond what the current validator already checks.

## Decisions

### Decision: `Request.size` becomes the single payload-length source

`Host.Memory.get_req_data()` will generate placeholder payloads using `req.size` for every request type that fetches host data. This matches the intended simulator model and removes the need to carry a second length field through request construction.

Alternative considered: keep `data_size` as a deprecated alias on `Request`. Rejected because it preserves duplicate state in the core request object and invites future divergence.

### Decision: remove pointer fields from request construction, but keep parser validation permissive

`parser.py` will stop listing `data_address` and `data_size` as required or optional schema members, and `Engine.Initialize_event_queue()` will stop reading them into `Request`. The validator will still accept commands that happen to contain extra legacy keys, because it already validates only required fields.

Alternative considered: add strict unknown-field rejection immediately. Rejected for this change because it would force a larger trace cleanup and add avoidable migration risk to a model simplification.

### Decision: update the in-repo trace generator that still emits removed fields

`flash_sim/trace_generation/gen_gc_test.py` will stop emitting the removed keys so newly generated traces reflect the simplified schema.

Alternative considered: leave generators untouched because legacy keys are ignored. Rejected because it would keep teaching the old interface.

## Design Rationale

The simulator has already abstracted away real payload storage, so keeping pointer metadata in `Request` no longer buys correctness or realism. Removing the fields at the request boundary is the cleanest way to align the data model with the simulator's actual behavior, while using `size` as the single source of truth keeps request construction and trace authoring simpler.

Keeping parser validation permissive is a deliberate trade-off: it lets existing traces continue to run during the transition, while new code and generated traces stop depending on the removed fields immediately.

## Risks / Trade-offs

- Legacy traces with inconsistent `data_size` values will now behave according to `size` only. -> Mitigation: document the change in proposal/specs and update in-repo generators to emit the new shape.
- Removing fields from `Request` could leave stale attribute access in less-traveled code paths. -> Mitigation: search the whole `flash_sim` package for both field names and update every direct reference.
- Parser behavior remains permissive for unknown extra keys. -> Mitigation: this is intentional for compatibility; a future cleanup can add stricter validation once trace migration is complete.

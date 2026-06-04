## Context

`PHY` models command transfer, array execution, and data transfer through scheduled simulator events. Normal write execution already classifies GC writes by inspecting `transactions[0].type.value.lower()` and always registers completion events with a dict payload containing `chip_id`, `die_id`, and `transactions`.

The crash reported with `test_case/test_trace.json` happens only on the suspend/resume path. `PHY._send_resume_command(...)` restores a suspended command and re-registers the completion event, but it currently diverges from the normal path in two ways:

- It checks `"gc" in transaction.type`, where `transaction.type` is a `TransactionType` enum.
- It schedules resume completion events with a tuple payload instead of the dict payload that `PHY.execute(...)` expects.
- It leaves the original pre-suspend completion event live in the event queue, which can cause the same write completion callback to fire twice after resume.

Because the generated trace mixes reads, writes, and GC pressure, it exercises the path where a read completes and triggers resume of a suspended write. That makes resume-path consistency the main constraint for this design.

## Goals / Non-Goals

**Goals:**

- Make resumed write and erase commands use the same transaction metadata conventions as the normal `PHY` command path.
- Preserve GC-aware chip status for resumed GC writes.
- Add a focused regression test that exercises resume behavior directly, plus confirm the end-to-end simulator run no longer aborts on the provided trace.

**Non-Goals:**

- Redesigning TSU scheduling or suspend heuristics.
- Changing request generation, preconditioning data, or GC policies.
- Refactoring unrelated `PHY` data transfer or storage persistence behavior.

## Decisions

1. Reuse the existing transaction-type normalization pattern on resume.
   Resume logic will inspect `transactions[0].type.value.lower()` or an equivalent helper-backed string rather than probing the enum object directly.

   Alternatives considered:
   - Compare only against `TransactionType.GC_WRITE`.
     Rejected because the rest of `PHY` already treats operation categories through normalized strings, and future GC-related write subtypes would be easier to handle consistently with string normalization.
   - Convert the enum with `str(transaction.type)`.
     Rejected because enum string formatting is less explicit than using `.value`, and the normal path already uses `.value.lower()`.

2. Normalize resume-generated event payloads to the same dict shape as all other `PHY` events.
   `PHY.execute(...)` already assumes `event.param` is a mapping and reads `chip_id`, `die_id`, and `transactions` with `.get(...)`. The resume path should conform to that contract instead of introducing a special-case tuple payload.

   Alternatives considered:
   - Teach `PHY.execute(...)` to accept both tuple and dict payloads.
     Rejected because it spreads resume-specific branching into the central event handler and makes future event additions easier to break.

3. Preserve a handle to scheduled write and erase completion events so suspend can invalidate stale events.
   The simulator already represents future work as `SimEvent` instances with an `ignored` flag. Returning the created event from the event scheduler and storing it on the in-flight transactions lets `DieBKE.prepare_suspend(...)` invalidate the old completion event before resume schedules a replacement.

   Alternatives considered:
   - Search the global event queue and delete matching events during suspend.
     Rejected because it couples `PHY` directly to engine internals and makes matching ambiguous when multiple similar events exist.
   - Tolerate duplicate completions and harden downstream callbacks.
     Rejected because it masks the scheduling bug and still risks double-persistence or duplicate AMU callbacks.

4. Add a direct regression around `_send_resume_command(...)` instead of relying only on the full simulator trace.
   The end-to-end trace is valuable for validation, but a focused unit-style test gives faster feedback and pins down the resume contract around chip status and event payload shape.

## Design Rationale

The bug is not a scheduling-policy problem; it is a contract drift problem inside `PHY`. The normal command path and the resume path should be interchangeable from the perspective of the event engine. Re-aligning resume behavior with the already-working normal path is the smallest, safest fix because it reduces special handling instead of adding more.

Keeping the regression close to `PHY` also lowers the debugging surface. If the tests assert GC detection, event payload structure, and stale-event invalidation, future resume changes will fail early before they surface as late simulator crashes.

## Risks / Trade-offs

- [Risk] Resume logic may still differ from the normal path in an unobserved branch. → Mitigation: compare resumed write/erase event registration against the normal write/erase branches and validate with both direct and end-to-end tests.
- [Risk] A focused regression may mock too much and miss integration issues. → Mitigation: keep the direct test narrow but also run `flash_sim/main.py` with `test_case/test_trace.json`.
- [Risk] Existing dirty-worktree changes may overlap nearby lines in `PHY.py`. → Mitigation: keep the patch minimal and avoid touching unrelated logic.

## Migration Plan

1. Update `PHY._send_resume_command(...)` to use normalized transaction-type inspection and dict-shaped event payloads.
2. Update suspend-time bookkeeping so the superseded completion event is marked ignored before the resumed command schedules a replacement.
3. Add regression coverage in `test_script/` for resumed command scheduling and stale-event invalidation.
4. Re-run the failing trace through `flash_sim/main.py`.
5. If verification passes, mark the change tasks complete. Rollback is straightforward because the fix is localized to resume handling and its tests.

## Open Questions

- None at the moment; the failure signature and the inconsistent resume-path contract are both concrete and reproducible.

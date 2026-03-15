import sys
import traceback

if __package__ in (None, ""):
    import os
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from flash_sim.engine import Engine
    from flash_sim.common import format_event_queue
else:
    from .engine import Engine
    from .common import format_event_queue


def _queue_snapshot(q):
    """获取 Queue 的当前元素快照（不消费）。"""
    try:
        return list(q.queue)
    except Exception:
        return []


def _heap_snapshot(pq):
    """获取 PriorityQueue 的当前堆快照（不消费）。"""
    try:
        return list(pq.queue)
    except Exception:
        return []


def print_all_module_data_structures(engine):
    """在 finally 中调用：打印所有模块中的数据结构对象。"""
    sep = "========================================"
    print(f"\n{sep}")
    print("所有模块数据结构汇总 (All Module Data Structures)")
    print(sep)

    # ----- Engine -----
    print("\n--- Engine ---")
    try:
        print(f"  current_time: {engine.Get_current_time()}")
        remaining = _heap_snapshot(engine.event_queue)
        print(f"  event_queue (remaining events): {len(remaining)}")
        for i, ev in enumerate(sorted(remaining, key=lambda e: (e.time, id(e)))):
            print(f"    [{i}] {ev}")
    except Exception as e:
        print(f"  (Engine dump error: {e})")

    # ----- Host -----
    print("\n--- Host ---")
    try:
        host = engine.host
        qp = host.queue_ptrs
        print(f"  queue_ptrs: sq_heads={qp.sq_heads}, sq_tails={qp.sq_tails}, cq_heads={qp.cq_heads}, cq_tails={qp.cq_tails}")
        print("  memory.sq_entries:")
        for sq_id, entries in enumerate(host.memory.sq_entries):
            print(f"    sq_id={sq_id}: {len(entries)} request(s)")
            for j, req in enumerate(entries):
                print(f"      [{j}] {req}")
        print("  io_flows:")
        for i, flow in enumerate(host.io_flows):
            cr = flow.current_req
            print(f"    flow[{i}] busy={flow.busy}, current_req={cr if cr is None else str(cr)}")
        waiting = _queue_snapshot(host.waiting_req)
        print(f"  waiting_req: {len(waiting)} item(s)")
        for j, req in enumerate(waiting):
            print(f"    [{j}] {req}")
    except Exception as e:
        print(f"  (Host dump error: {e})")

    # ----- Device (HIL, FTL, PHY) -----
    print("\n--- Device (HIL) ---")
    try:
        hil = engine.device.hil
        print(f"  _sq_head_tail: {hil._sq_head_tail}, _cq_head_tail: {hil._cq_head_tail}")
        print("  input_streams:")
        for sq_id, q in enumerate(hil.input_streams):
            items = _queue_snapshot(q)
            print(f"    sq_id={sq_id}: {len(items)} item(s)")
            for j, obj in enumerate(items):
                print(f"      [{j}] {obj}")
    except Exception as e:
        print(f"  (Device/HIL dump error: {e})")

    print("\n--- Device (FTL) ---")
    try:
        ftl = engine.device.ftl
        amu = getattr(ftl, "address_mapping_unit", None)
        if amu is not None and hasattr(amu, "gtd"):
            gtd = amu.gtd
            print(f"  address_mapping_unit.gtd: {len(gtd)} entry(ies)")
            for k, v in list(gtd.items())[:10]:
                print(f"    {k} -> {v}")
            if len(gtd) > 10:
                print(f"    ... and {len(gtd) - 10} more")
        bm = getattr(ftl, "block_manager", None)
        if bm is not None:
            print(f"  block_manager: {bm}")
    except Exception as e:
        print(f"  (Device/FTL dump error: {e})")

    print("\n--- Device (PHY) ---")
    try:
        phy = engine.device.phy
        for attr in ("channels", "active_commands", "pending_read", "pending_write"):
            if hasattr(phy, attr):
                val = getattr(phy, attr)
                print(f"  {attr}: {val}")
    except Exception as e:
        print(f"  (Device/PHY dump error: {e})")

    # ----- PCIe_link -----
    print("\n--- PCIe_link ---")
    try:
        link = engine.pcie_link
        h2d = _queue_snapshot(link.host_to_device_queue)
        d2h = _queue_snapshot(link.device_to_host_queue)
        print(f"  host_to_device_queue: {len(h2d)} message(s)")
        for j, msg in enumerate(h2d):
            print(f"    [{j}] {msg}")
        print(f"  device_to_host_queue: {len(d2h)} message(s)")
        for j, msg in enumerate(d2h):
            print(f"    [{j}] {msg}")
    except Exception as e:
        print(f"  (PCIe_link dump error: {e})")

    print(f"\n{sep}\n")


if __name__ == "__main__":
    # 禁止缓冲，使 print 立即输出（便于日志/重定向时实时查看）
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    sim_engine = Engine()
    print("Module construction complete.\n\n")
    try:
        sim_engine.Start_simulation(r"E:\Files\Li_Meng\HBF\Flash-Sim\examples\test_trace.json")
    except Exception as e:
        print(f"Error: {e}")
        try:
            print("address_mapping_unit.gtd:", sim_engine.device.ftl.address_mapping_unit.gtd)
        except Exception as _:
            print("(address_mapping_unit.gtd not available:", _)
        print("\n--- Traceback (most recent call last) ---")
        traceback.print_exc()
    finally:
        print("Simulation completed.")
        print(f"Simulation time: {sim_engine.Get_current_time()}")
        print(format_event_queue(sim_engine.event_queue.queue))
        print_all_module_data_structures(sim_engine)

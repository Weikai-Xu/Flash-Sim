from flash_sim.common import GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD, SECTOR_PER_PAGE

from test_script.generate_test_trace import (
    build_runtime_context,
    estimate_gc_pressure_write_count,
    generate_trace,
    plane_key_for_random_access_lpa,
)


def test_generate_trace_gc_pressure_tracks_live_plane_state():
    context = build_runtime_context()
    generated = generate_trace(seed=53, request_budget=12)

    plane_map = context.plane_map
    target_plane = plane_map[generated.summary.target_plane]

    assert target_plane.free_block_count > GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD
    assert (
        generated.summary.required_gc_pressure_writes
        == estimate_gc_pressure_write_count(target_plane)
    )

    target_plane_write_lpas = [
        command["start_lha"] // SECTOR_PER_PAGE
        for command in generated.commands
        if command["type"] == "write"
        and plane_key_for_random_access_lpa(command["start_lha"] // SECTOR_PER_PAGE)
        == generated.summary.target_plane
    ]

    assert len(target_plane_write_lpas) == generated.summary.required_gc_pressure_writes

    if target_plane.invalid_page_count == 0:
        assert set(target_plane_write_lpas) & set(target_plane.valid_lpas)

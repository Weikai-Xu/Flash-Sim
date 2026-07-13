import pytest

from flash_sim.common import (
    CMT_SIZE,
    LPA_NO_PER_MAPPING_PAGE,
    REQUEST_STATUS_SUCCESS,
    RequestType,
    SECTOR_PER_PAGE,
)
from flash_sim.config import build_flash_config_for_capacity
from flash_sim.engine import Engine


def test_required_range_preconditioning_warms_full_cmt_and_keeps_overflow_mapping():
    engine = Engine({"runtime": {"cache_bypass": True}})
    required_pages = CMT_SIZE + 2

    engine.initialize_in_process(
        required_lha_ranges=[
            {"start_lha": 0, "size": required_pages * SECTOR_PER_PAGE}
        ]
    )

    amu = engine.device.ftl.address_mapping_unit
    assert len(amu.cmt.cache) == CMT_SIZE
    assert set(range(CMT_SIZE)).issubset(amu.cmt.cache)

    overflow_lpa = CMT_SIZE + 1
    assert overflow_lpa not in amu.cmt.cache
    mvpn = overflow_lpa // LPA_NO_PER_MAPPING_PAGE
    assert mvpn in amu.gtd

    mapping_addr = amu.gtd[mvpn].address
    mapping_page = engine.device.ftl.tsu.phy._storage[mapping_addr.channel][mapping_addr.chip][mapping_addr.die][mapping_addr.plane][mapping_addr.sub_plane][mapping_addr.page]
    assert mapping_page.valid_bitmap[overflow_lpa % LPA_NO_PER_MAPPING_PAGE] == 1

    stats = engine.device.ftl.block_manager.last_precondition_stats
    assert stats["mode"] == "required-ranges"
    assert stats["required_mapping_count"] == required_pages
    assert stats["cmt_warm_pages"] == CMT_SIZE


def test_required_range_preconditioning_rejects_out_of_capacity_range():
    engine = Engine({"runtime": {"cache_bypass": True}})
    amu = engine.device.ftl.address_mapping_unit
    invalid_start_lha = amu.random_access_data_pages * SECTOR_PER_PAGE

    with pytest.raises(ValueError, match="outside capacity"):
        engine.initialize_in_process(
            required_lha_ranges=[{"start_lha": invalid_start_lha, "size": SECTOR_PER_PAGE}]
        )


def test_in_memory_request_result_extraction_without_report_file():
    engine = Engine({"runtime": {"cache_bypass": True}})
    req = engine.make_request(
        RequestType.READ,
        lha_start=0,
        size=1,
        report_req_id="unit-read",
    )

    engine.request_latency_recorder.register_request(req, 5)
    engine.request_latency_recorder.note_req_init_executed(req, 5)
    engine.current_time = 17
    req.status = REQUEST_STATUS_SUCCESS
    engine.request_latency_recorder.note_request_completed(req, 17)

    record = engine.get_request_record(req)
    result = engine.get_request_result(req)

    assert record["req_id"] == "unit-read"
    assert record["status"] == REQUEST_STATUS_SUCCESS
    assert record["total_latency"] == 12
    assert result["latency"] == 12
    assert result["status"] == REQUEST_STATUS_SUCCESS


def test_engine_uses_generated_capacity_config_before_preconditioning():
    config, report = build_flash_config_for_capacity(
        {
            "geometry": {
                "channel_no": 1,
                "chip_per_channel": 2,
                "dies": 1,
                "planes_per_die": 1,
                "blocks_per_plane": 1,
                "layers_per_block": 8,
                "sl_per_block": 1,
                "ssl_per_sl": 1,
                "sub_blocks_per_block": 1,
                "sector_per_page": SECTOR_PER_PAGE,
                "static_chip_per_channel": 1,
            },
            "runtime": {"cache_bypass": True},
        },
        required_sectors=SECTOR_PER_PAGE * 4,
        capacity_margin=0.0,
    )
    engine = Engine(config)
    amu = engine.device.ftl.address_mapping_unit
    generated_capacity = amu.random_access_data_pages * engine.config.geometry.sector_per_page

    assert generated_capacity >= report["required_target_sectors"]
    engine.initialize_in_process(
        required_lha_ranges=[{"start_lha": 0, "size": SECTOR_PER_PAGE * 4}]
    )
    assert engine.device.ftl.block_manager.last_precondition_stats["required_mapping_count"] == 4

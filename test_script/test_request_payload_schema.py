import pytest

from flash_sim.Host import Host
from flash_sim.common import Request, RequestType
from flash_sim.parser import parse_trace


def test_parse_trace_accepts_size_only_data_commands():
    trace = """
    [
      {"type": "write", "time": 0, "start_lha": 0, "size": 4},
      {"type": "static_write", "time": 1, "start_lha": 64, "size": 1},
      {"type": "search", "time": 2, "start_lha": 1610612736, "size": 2},
      {"type": "compute", "time": 3, "start_lha": 1610612800, "size": 3}
    ]
    """

    commands = parse_trace(trace)

    assert [cmd["type"] for cmd in commands] == ["write", "static_write", "search", "compute"]


def test_parse_trace_keeps_legacy_extra_fields_backward_compatible():
    trace = """
    [
      {"type": "search", "time": 0, "start_lha": 1610612736, "size": 1, "data_address": -1, "data_size": 1}
    ]
    """

    commands = parse_trace(trace)

    assert commands[0]["size"] == 1


@pytest.mark.parametrize(
    "req_type,size",
    [
        (RequestType.WRITE, 4),
        (RequestType.SEARCH, 2),
        (RequestType.COMPUTE, 3),
        (RequestType.STATIC_WRITE, 1),
    ],
)
def test_host_memory_payload_length_comes_from_request_size(req_type, size):
    memory = Host.Memory()
    req = Request(type=req_type, size=size)

    data = memory.get_req_data(req)

    assert data == [11] * size

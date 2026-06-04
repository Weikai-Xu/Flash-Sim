import flash_sim.PHY as phy_module
from flash_sim.common import (
    ChipStatus,
    EventType,
    FlashAddress,
    SimEvent,
    Transaction,
    TransactionType,
)


def _make_transaction(transaction_type: TransactionType) -> Transaction:
    return Transaction(
        source_req=None,
        type=transaction_type,
        address=FlashAddress(channel=0, chip=0, die=0, plane=0, sub_plane=0, page=0),
    )


def _resume_and_capture(monkeypatch, command_type: str, transaction_type: TransactionType):
    events = []
    phy = phy_module.PHY()
    chip_id = (0, 0)
    die_id = 0
    chip_bke = phy.get_chip_bke(chip_id)
    die_bke = chip_bke.get_die_bke(die_id)
    transaction = _make_transaction(transaction_type)
    transactions = [transaction]

    monkeypatch.setattr(phy_module, "CURRENT_TIME", lambda: 1_000)
    monkeypatch.setattr(
        phy_module,
        "Register_event",
        lambda event_type, target, param, scheduled_time: events.append(
            (event_type, target, param, scheduled_time)
        ),
    )

    die_bke.suspended_command = phy_module.ActiveCommandInfo(command_type, transactions)
    die_bke._remaining_on_suspend = 123
    chip_bke.HasSuspendedCommands = True

    phy._send_resume_command(chip_id)

    assert die_bke.suspended_command is None
    assert chip_bke.HasSuspendedCommands is False
    assert len(events) == 1
    return phy, chip_bke, die_bke, transactions, events[0]


def test_send_resume_command_restores_write_status_and_event_payload(monkeypatch):
    cases = [
        (TransactionType.GC_WRITE, ChipStatus.GC_WRITE),
        (TransactionType.USER_WRITE, ChipStatus.WRITE),
        (TransactionType.MAPPING_WRITE, ChipStatus.WRITE),
    ]

    for transaction_type, expected_status in cases:
        _, chip_bke, die_bke, transactions, event = _resume_and_capture(
            monkeypatch, "write", transaction_type
        )
        event_type, _, param, scheduled_time = event

        assert chip_bke.status is expected_status
        assert die_bke.expected_finish_time == 1_123
        assert chip_bke.Expected_Finish_Time == 1_123
        assert event_type is EventType.PHY_CHIP_WRITE_COMPLETE
        assert scheduled_time == 1_123
        assert param == {
            "chip_id": (0, 0),
            "die_id": 0,
            "transactions": transactions,
        }


def test_send_resume_command_restores_erase_event_payload(monkeypatch):
    _, chip_bke, die_bke, transactions, event = _resume_and_capture(
        monkeypatch, "erase", TransactionType.GC_ERASE
    )
    event_type, _, param, scheduled_time = event

    assert chip_bke.status is ChipStatus.ERASE
    assert die_bke.expected_finish_time == 1_123
    assert chip_bke.Expected_Finish_Time == 1_123
    assert event_type is EventType.PHY_CHIP_ERASE_COMPLETE
    assert scheduled_time == 1_123
    assert param == {
        "chip_id": (0, 0),
        "die_id": 0,
        "transactions": transactions,
    }


def test_prepare_suspend_ignores_stale_completion_event():
    phy = phy_module.PHY()
    chip_bke = phy.get_chip_bke((0, 0))
    die_bke = chip_bke.get_die_bke(0)
    transaction = _make_transaction(TransactionType.MAPPING_WRITE)
    scheduled_event = SimEvent(
        type=EventType.PHY_CHIP_WRITE_COMPLETE,
        target=phy,
        time=2_000,
        param={"chip_id": (0, 0), "die_id": 0, "transactions": [transaction]},
    )
    transaction.exec_event = scheduled_event
    die_bke.active_command = phy_module.ActiveCommandInfo("write", [transaction])
    die_bke.expected_finish_time = 2_000

    die_bke.prepare_suspend(1_500)

    assert scheduled_event.ignored is True
    assert transaction.exec_event is None
    assert die_bke._remaining_on_suspend == 500
    assert die_bke.active_command is None
    assert die_bke.suspended_command is not None

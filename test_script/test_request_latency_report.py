import unittest

from flash_sim.common import Request, RequestType, Transaction, TransactionType
from flash_sim.request_latency_report import (
    BASE_STAGE_NAMES,
    RECONCILIATION_STAGE_NAMES,
    RequestLatencyRecorder,
)


class TestRequestLatencyRecorder(unittest.TestCase):
    def _make_req(self, req_type=RequestType.READ, req_id="req-0"):
        return Request(
            type=req_type,
            lha_start=0,
            size=1,
            trace_index=0,
            trace_time=0,
            report_req_id=req_id,
        )

    def test_breakdown_reconciles_overlap_and_keeps_skipped_stages_zero(self):
        recorder = RequestLatencyRecorder()
        req = self._make_req(RequestType.READ, "req-overlap")
        recorder.register_request(req, scheduled_time=0)
        recorder.note_req_init_executed(req, 0)
        recorder.note_request_completed(req, 10)

        rec = recorder.requests[req.report_req_id]
        recorder._append_interval(rec, "intervals", "pcie_host_to_device", 0, 5)
        recorder._append_interval(rec, "intervals", "phy_array_exec", 3, 8)

        exported = recorder.export()["requests"][0]
        breakdown = exported["breakdown"]

        self.assertEqual(exported["total_latency"], 10)
        self.assertEqual(breakdown["pcie_host_to_device"], 5)
        self.assertEqual(breakdown["phy_array_exec"], 5)
        self.assertEqual(breakdown["overlap_latency"], 2)
        self.assertEqual(breakdown["untracked_latency"], 2)

        for stage in BASE_STAGE_NAMES:
            if stage not in {"pcie_host_to_device", "phy_array_exec"}:
                self.assertEqual(breakdown[stage], 0)
        for stage in RECONCILIATION_STAGE_NAMES:
            self.assertIn(stage, breakdown)

    def test_write_without_persistence_completion_is_marked_superseded(self):
        recorder = RequestLatencyRecorder()
        req = self._make_req(RequestType.WRITE, "req-superseded")
        recorder.register_request(req, scheduled_time=0)
        recorder.note_req_init_executed(req, 0)
        recorder.note_request_completed(req, 40)

        exported = recorder.export()["requests"][0]

        self.assertEqual(exported["host_total_latency"], 40)
        self.assertEqual(exported["persistence_status"], "superseded_in_cache")
        self.assertEqual(exported["persistence_total_latency"], 0)
        self.assertTrue(
            all(value == 0 for value in exported["persistence_breakdown"].values())
        )

    def test_background_flush_lineage_marks_write_as_persisted(self):
        recorder = RequestLatencyRecorder()
        req = self._make_req(RequestType.WRITE, "req-persisted")
        recorder.register_request(req, scheduled_time=0)
        recorder.note_req_init_executed(req, 0)
        recorder.note_request_completed(req, 30)

        flush_tr = Transaction(
            source_req=None,
            type=TransactionType.USER_WRITE,
            lpa=0,
            report_origin_request_ids=[req.report_req_id],
        )
        recorder.note_tsu_enqueued(flush_tr, 30)
        recorder.note_tsu_dispatched(flush_tr, 40)
        recorder.note_phy_command_phase(
            [flush_tr],
            op_kind="write",
            start_time=40,
            finish_time=240,
            cmd_addr_time=100,
        )
        recorder.note_phy_array_phase(
            [flush_tr],
            op_kind="write",
            start_time=240,
            finish_time=640,
        )
        recorder.note_persistence_completed(flush_tr, 640)

        exported = recorder.export()["requests"][0]
        breakdown = exported["persistence_breakdown"]

        self.assertEqual(exported["persistence_status"], "persisted")
        self.assertEqual(exported["persistence_total_latency"], 640)
        self.assertEqual(breakdown["tsu_queue_wait"], 10)
        self.assertEqual(breakdown["phy_cmd_addr"], 100)
        self.assertEqual(breakdown["phy_data_in"], 100)
        self.assertEqual(breakdown["phy_array_exec"], 400)
        self.assertEqual(breakdown["phy_data_out"], 0)


if __name__ == "__main__":
    unittest.main()

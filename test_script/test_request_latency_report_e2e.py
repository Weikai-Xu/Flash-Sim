import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from flash_sim.engine import Engine


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_CASE_DIR = REPO_ROOT / "test_case"


def _run_engine_and_load_report(trace_content, trace_name):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        trace_path = tmpdir_path / trace_name
        trace_path.write_text(json.dumps(trace_content), encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            engine = Engine()
            engine.Start_simulation(str(trace_path))

        report_path = engine.last_request_latency_report_path
        if report_path is None or not report_path.exists():
            raise AssertionError("expected request latency report to be generated")
        try:
            return json.loads(report_path.read_text(encoding="utf-8")), buf.getvalue()
        finally:
            report_path.unlink()


class TestRequestLatencyReportEndToEnd(unittest.TestCase):
    def test_mapping_miss_read_exports_expected_host_and_phy_stages(self):
        trace_content = json.loads((TEST_CASE_DIR / "test_read.json").read_text(encoding="utf-8"))
        report, output = _run_engine_and_load_report(trace_content, "single_read_trace.json")

        self.assertNotIn("Traceback", output)
        self.assertEqual(report["meta"]["request_count"], 1)
        req = report["requests"][0]

        self.assertEqual(req["type"], "READ")
        self.assertEqual(req["persistence_status"], "not_applicable")
        self.assertGreater(req["breakdown"]["pcie_host_to_device"], 0)
        self.assertGreater(req["breakdown"]["pcie_device_to_host"], 0)
        self.assertGreater(req["breakdown"]["amu_mapping_wait"], 0)
        self.assertGreater(req["breakdown"]["phy_cmd_addr"], 0)
        self.assertGreater(req["breakdown"]["phy_array_exec"], 0)
        self.assertGreater(req["breakdown"]["phy_data_out"], 0)

    def test_read_queue_contention_exports_non_zero_tsu_wait(self):
        trace_content = [
            {"type": "read", "time": 0, "start_lha": 106688, "size": 1},
            {"type": "read", "time": 0, "start_lha": 106688, "size": 1},
        ]
        report, output = _run_engine_and_load_report(trace_content, "read_queue_trace.json")

        self.assertNotIn("Traceback", output)
        self.assertEqual(report["meta"]["request_count"], 2)
        self.assertTrue(
            any(req["breakdown"]["amu_mapping_wait"] > 0 for req in report["requests"])
        )
        self.assertTrue(
            any(req["breakdown"]["tsu_queue_wait"] > 0 for req in report["requests"])
        )
        self.assertTrue(
            all(req["breakdown"]["phy_cmd_addr"] > 0 for req in report["requests"])
        )
        self.assertTrue(
            all(req["breakdown"]["phy_array_exec"] > 0 for req in report["requests"])
        )
        self.assertTrue(
            all(req["breakdown"]["phy_data_out"] > 0 for req in report["requests"])
        )

    def test_write_report_distinguishes_host_completion_from_persistence(self):
        trace_content = json.loads((TEST_CASE_DIR / "test_write.json").read_text(encoding="utf-8"))
        report, output = _run_engine_and_load_report(trace_content, "single_write_trace.json")

        self.assertNotIn("Traceback", output)
        self.assertEqual(report["meta"]["request_count"], 1)
        req = report["requests"][0]

        self.assertEqual(req["type"], "WRITE")
        self.assertGreater(req["host_total_latency"], 0)
        self.assertGreater(req["breakdown"]["pcie_host_to_device"], 0)
        self.assertGreater(req["breakdown"]["pcie_device_to_host"], 0)
        self.assertEqual(req["persistence_status"], "persisted")
        self.assertGreater(req["persistence_total_latency"], req["host_total_latency"])
        self.assertGreater(req["persistence_breakdown"]["phy_cmd_addr"], 0)
        self.assertGreater(req["persistence_breakdown"]["phy_data_in"], 0)
        self.assertGreater(req["persistence_breakdown"]["phy_array_exec"], 0)


if __name__ == "__main__":
    unittest.main()

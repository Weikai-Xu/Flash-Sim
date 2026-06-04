import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestReadWriteTrace(unittest.TestCase):
    def test_main_trace_read_after_write_completes_without_mapping_error(self):
        repo_root = Path(__file__).resolve().parents[1]
        source_trace = repo_root / "test_case" / "test_read_write.json"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            trace_path = tmpdir_path / "read_write_main_trace.json"
            trace_path.write_text(source_trace.read_text(encoding="utf-8"), encoding="utf-8")
            log_path = tmpdir_path / "read_write_main_trace.log"
            report_path = repo_root / "report" / "read_write_main_trace_request_latency.json"

            try:
                proc = subprocess.run(
                    [sys.executable, "flash_sim/main.py"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                    env={
                        **os.environ,
                        "FLASH_SIM_INPUT_JSON": str(trace_path),
                        "FLASH_SIM_MERGED_LOG": str(log_path),
                        "FLASH_SIM_MIRROR_CONSOLE": "0",
                    },
                )

                log_output = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
                combined = proc.stdout + proc.stderr + log_output
                self.assertEqual(proc.returncode, 0, msg=combined)
                self.assertNotIn("Read request accessing non-existing mapping page", combined)
                self.assertNotIn("Error:", combined)
                self.assertIn("Request latency report:", combined)
                self.assertTrue(log_path.exists(), msg="expected merged log to be generated")
                self.assertTrue(report_path.exists(), msg="expected request latency report to be generated")

                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(report["meta"]["request_count"], 2)
                self.assertEqual(
                    [req["type"] for req in report["requests"]],
                    ["WRITE", "READ"],
                )
            finally:
                if report_path.exists():
                    report_path.unlink()


if __name__ == "__main__":
    unittest.main()

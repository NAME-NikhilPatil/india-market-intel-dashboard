from pathlib import Path
import sys
import tempfile
import time
import unittest

from process_runner import run_step


class JobTimeoutTests(unittest.TestCase):
    def test_run_step_terminates_a_timed_out_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "timeout.log"
            started = time.monotonic()
            with log_path.open("w", encoding="utf-8") as log:
                code = run_step(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    Path(tmp),
                    log,
                    timeout_seconds=1,
                )

            self.assertEqual(124, code)
            self.assertLess(time.monotonic() - started, 8)
            self.assertIn("step timed out after 1 seconds", log_path.read_text(encoding="utf-8"))

    def test_run_step_returns_success_before_the_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "success.log"
            with log_path.open("w", encoding="utf-8") as log:
                code = run_step(
                    [sys.executable, "-c", "print('ok')"],
                    Path(tmp),
                    log,
                    timeout_seconds=5,
                )

            self.assertEqual(0, code)
            self.assertIn("ok", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

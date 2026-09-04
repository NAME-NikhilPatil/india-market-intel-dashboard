import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from selenium.common.exceptions import StaleElementReferenceException


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "vahan_dashboard_project" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from vahan_harvest import Harvester  # noqa: E402


class _RerenderedTable:
    @property
    def text(self):
        raise StaleElementReferenceException("table was replaced by VAHAN")


class _DynamicDriver:
    def __init__(self):
        self.table_text_reads = 0

    def find_elements(self, by, value):
        return [_RerenderedTable()] if value == "groupingTable" else []

    def find_element(self, by, value):
        return _RerenderedTable()

    def execute_script(self, script, *args):
        if "return !!document.getElementById" in script:
            return True
        if "innerText" in script or "textContent" in script:
            self.table_text_reads += 1
            return "before" if self.table_text_reads == 1 else "after"
        return None


class _ImmediateWait:
    def __init__(self, driver):
        self.driver = driver

    def until(self, condition):
        return condition(self.driver)


class VahanHarvesterTests(unittest.TestCase):
    def test_click_refresh_survives_table_replacement(self):
        harvester = Harvester.__new__(Harvester)
        harvester.driver = _DynamicDriver()
        harvester.wait = _ImmediateWait(harvester.driver)
        harvester.job = SimpleNamespace(delay=0)
        harvester.wait_idle = lambda: None

        try:
            harvester.click_refresh("j_idt80")
        except StaleElementReferenceException as exc:
            self.fail(f"click_refresh leaked a transient stale-table race: {exc}")

        self.assertGreaterEqual(harvester.driver.table_text_reads, 2)


if __name__ == "__main__":
    unittest.main()

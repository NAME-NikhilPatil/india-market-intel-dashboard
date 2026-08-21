from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIVE_APP_NAME = "india-market-dashboard-v2-vin"


class DeploymentContractTests(unittest.TestCase):
    def test_azure_workflows_target_the_live_app_service(self) -> None:
        for relative_path in (
            ".github/workflows/azure-app-service-container.yml",
            ".github/workflows/daily-scrape.yml",
        ):
            workflow = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(
                f"AZURE_APP_NAME: {LIVE_APP_NAME}",
                workflow,
                f"{relative_path} must deploy to and refresh the live App Service",
            )

    def test_ev_stairway_uses_the_generated_payload_schema(self) -> None:
        dashboard = (
            ROOT / "vahan_dashboard_project" / "vahan_dashboard_v19.html"
        ).read_text(encoding="utf-8")
        start = dashboard.index("function renderEvStairway()")
        end = dashboard.index("// MAKER FOCUS PANEL", start)
        renderer = dashboard[start:end]

        self.assertIn("row.by_year[String(yr)]", renderer)
        self.assertIn("row.latest_cum_ev", renderer)
        self.assertNotIn("row.per_year[String(yr)]", renderer)
        self.assertNotIn("row.latest_ev", renderer)


if __name__ == "__main__":
    unittest.main()

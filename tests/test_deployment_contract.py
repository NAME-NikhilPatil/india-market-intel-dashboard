from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIVE_APP_NAME = "india-market-dashboard-v2-vin"


class DeploymentContractTests(unittest.TestCase):
    def test_azure_deployment_targets_the_live_app_service(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "azure-app-service-container.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(f"AZURE_APP_NAME: {LIVE_APP_NAME}", workflow)
        self.assertIn("AZURE_ACR_NAME: acrindiamarketdashv", workflow)

    def test_container_build_runs_inside_azure_container_registry(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "azure-app-service-container.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("az acr build", workflow)
        self.assertNotIn("az acr login", workflow)
        self.assertNotIn("docker push", workflow)

    def test_daily_scraper_uses_the_live_https_endpoint_without_azure_login(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "daily-scrape.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            f"APP_BASE_URL: https://{LIVE_APP_NAME}.azurewebsites.net",
            workflow,
        )
        self.assertNotIn("azure/login", workflow)
        self.assertNotIn("az webapp show", workflow)
        self.assertIn("/api/jobs/$JOB_ID", workflow)

    def test_only_github_actions_runs_the_production_schedule(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "azure-app-service-container.yml"
        ).read_text(encoding="utf-8")
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        startup = (ROOT / "startup.sh").read_text(encoding="utf-8")

        self.assertIn("ENABLE_SCRAPER_SCHEDULER=false", workflow)
        self.assertIn("ENABLE_SCRAPER_SCHEDULER=false", dockerfile)
        self.assertIn("ENABLE_SCRAPER_SCHEDULER:-false", startup)

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

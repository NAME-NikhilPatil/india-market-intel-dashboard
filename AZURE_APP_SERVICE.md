# Azure App Service Deployment

This folder can now run as a single Azure App Service custom container:

- Flask serves the one-page dashboard switcher.
- The existing dashboard HTML files are served from the same app.
- Scraper/rebuild jobs are available through protected API endpoints.
- The Docker image includes Chromium and ChromeDriver for VAHAN Selenium scraping.
- Runtime scrape outputs are written to Azure's persistent `/home` storage area.

If you prefer clicking through Azure Portal instead of using Azure CLI, use:

- `AZURE_PORTAL_DEPLOYMENT.md`

## Why Custom Container

VAHAN scraping uses Selenium. A plain Python App Service runtime may not include a browser, so this project uses `Dockerfile` to install:

- Python 3.12
- Chromium
- Chromium Driver
- Python dependencies from `requirements.txt`

The app starts with:

```sh
gunicorn app:app --bind 0.0.0.0:$PORT
```

## Runtime Architecture

Image seed folder:

```text
/app
```

Persistent Azure workspace:

```text
/home/site/dashboard-workspace
```

Persistent job logs/status:

```text
/home/site/scraper-runtime
```

On first startup, the app copies the dashboards, scraper scripts, and active data into the persistent workspace. Later scrapes update the persistent workspace, so refreshed dashboard HTML survives container restarts as long as App Service storage is enabled.

## Frontend Routes

```text
/                                      one-page dashboard switcher
/vahan_dashboard_project/vahan_dashboard_v19.html
/solar_dcr_scrape/solar_dcr_dashboard.html
```

## Scraper API

Set `SCRAPER_ADMIN_TOKEN` in Azure App Settings. The frontend will ask for this token when you press scraper buttons.

```text
GET  /api/health
GET  /api/scripts
POST /api/scripts/run
GET  /api/jobs
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/log
POST /api/scrape/solar
POST /api/rebuild/solar
POST /api/scrape/vahan/recent
POST /api/rebuild/vahan
```

For API calls outside the frontend, pass:

```text
X-Admin-Token: your-token
```

Advanced script runner example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "https://<app-name>.azurewebsites.net/api/scripts/run" `
  -Headers @{ "X-Admin-Token" = "<token>" } `
  -ContentType "application/json" `
  -Body '{"project":"vahan","script":"refresh_vahan_recent_months.py","args":["--sequential"]}'
```

This endpoint only runs Python files already present in `solar_dcr_scrape/` or `vahan_dashboard_project/scripts/`.

## Recommended App Settings

```text
WEBSITES_ENABLE_APP_SERVICE_STORAGE=true
WEBSITES_PORT=8000
SCRAPER_ADMIN_TOKEN=<strong random token>
SCRAPER_WORKSPACE_DIR=/home/site/dashboard-workspace
SCRAPER_RUNTIME_DIR=/home/site/scraper-runtime
CHROME_BIN=/usr/bin/chromium
WEB_CONCURRENCY=1
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=900
VAHAN_DELAY=0.4
VAHAN_ATTEMPTS=4
VAHAN_WAIT_SECONDS=120
VAHAN_PAGE_TIMEOUT=120
VAHAN_RETRY_SLEEP=8
ENABLE_SCRAPER_SCHEDULER=true
SOLAR_DAILY_UTC=21:30
VAHAN_DAILY_UTC=22:30
```

Daily scheduler timing:

```text
SOLAR_DAILY_UTC=21:30 -> 03:00 IST
VAHAN_DAILY_UTC=22:30 -> 04:00 IST
```

Keep the App Service scaled to one instance if you use the in-app scheduler, otherwise multiple instances can trigger duplicate jobs.

## Deploy With Azure CLI

Replace the names with globally unique values.

```powershell
$rg = "rg-india-market-intel"
$location = "centralindia"
$acr = "indiamarketintelacr"
$plan = "asp-india-market-intel"
$app = "india-market-intel-app"
$image = "$acr.azurecr.io/india-market-intel:latest"
$token = "replace-with-a-strong-token"

az group create --name $rg --location $location

az acr create `
  --resource-group $rg `
  --name $acr `
  --sku Basic `
  --admin-enabled true

az acr login --name $acr

docker build -t $image .
docker push $image

az appservice plan create `
  --name $plan `
  --resource-group $rg `
  --is-linux `
  --sku P1V3

az webapp create `
  --resource-group $rg `
  --plan $plan `
  --name $app `
  --deployment-container-image-name $image

$acrCred = az acr credential show --name $acr | ConvertFrom-Json
$acrUser = $acrCred.username
$acrPass = $acrCred.passwords[0].value

az webapp config container set `
  --name $app `
  --resource-group $rg `
  --docker-custom-image-name $image `
  --docker-registry-server-url "https://$acr.azurecr.io" `
  --docker-registry-server-user $acrUser `
  --docker-registry-server-password $acrPass

az webapp config appsettings set `
  --name $app `
  --resource-group $rg `
  --settings `
    WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
    WEBSITES_PORT=8000 `
    SCRAPER_ADMIN_TOKEN=$token `
    SCRAPER_WORKSPACE_DIR=/home/site/dashboard-workspace `
    SCRAPER_RUNTIME_DIR=/home/site/scraper-runtime `
    CHROME_BIN=/usr/bin/chromium `
    WEB_CONCURRENCY=1 `
    GUNICORN_TIMEOUT=900 `
    VAHAN_DELAY=0.4 `
    VAHAN_ATTEMPTS=4 `
    VAHAN_WAIT_SECONDS=120 `
    VAHAN_PAGE_TIMEOUT=120 `
    VAHAN_RETRY_SLEEP=8

az webapp config set `
  --name $app `
  --resource-group $rg `
  --always-on true

az webapp restart --name $app --resource-group $rg
```

Open:

```text
https://<app-name>.azurewebsites.net/
```

## Deploy With GitHub Actions

The workflow is already in:

```text
.github/workflows/azure-app-service-container.yml
```

It runs on every push to `main` and can also be started manually from the GitHub Actions tab.

### One-Time Azure Setup

Set your values:

```powershell
$subscriptionId = "<your-subscription-id>"
$tenantId = "<your-tenant-id>"
$rg = "rg-india-market-intel"
$location = "centralindia"
$acr = "indiamarketintelacr"
$plan = "asp-india-market-intel"
$app = "india-market-intel-app"
$githubOrg = "<your-github-username-or-org>"
$githubRepo = "<your-repo-name>"
```

Create Azure resources:

```powershell
az login
az account set --subscription $subscriptionId

az group create --name $rg --location $location

az acr create `
  --resource-group $rg `
  --name $acr `
  --sku Basic `
  --admin-enabled true

az appservice plan create `
  --name $plan `
  --resource-group $rg `
  --is-linux `
  --sku P1V3

az webapp create `
  --resource-group $rg `
  --plan $plan `
  --name $app `
  --deployment-container-image-name "mcr.microsoft.com/appsvc/staticsite:latest"

az webapp config appsettings set `
  --name $app `
  --resource-group $rg `
  --settings WEBSITES_ENABLE_APP_SERVICE_STORAGE=true WEBSITES_PORT=8000

az webapp config set `
  --name $app `
  --resource-group $rg `
  --always-on true
```

### One-Time GitHub OIDC Setup

Create an Entra app registration/service principal for GitHub Actions:

```powershell
$appRegistration = az ad app create --display-name "gh-$githubRepo-azure-deploy" | ConvertFrom-Json
$clientId = $appRegistration.appId

$sp = az ad sp create --id $clientId | ConvertFrom-Json
```

Give it access to the resource group:

```powershell
az role assignment create `
  --assignee $clientId `
  --role Contributor `
  --scope "/subscriptions/$subscriptionId/resourceGroups/$rg"

az role assignment create `
  --assignee $clientId `
  --role AcrPush `
  --scope "/subscriptions/$subscriptionId/resourceGroups/$rg/providers/Microsoft.ContainerRegistry/registries/$acr"
```

Allow GitHub Actions on `main` to authenticate without a password:

```powershell
az ad app federated-credential create `
  --id $clientId `
  --parameters "{`"name`":`"github-main`",`"issuer`":`"https://token.actions.githubusercontent.com`",`"subject`":`"repo:$githubOrg/$githubRepo:ref:refs/heads/main`",`"audiences`":[`"api://AzureADTokenExchange`"]}"
```

### GitHub Secrets

In GitHub:

```text
Repository -> Settings -> Secrets and variables -> Actions -> New repository secret
```

Add:

```text
AZURE_CLIENT_ID          = service principal client id
AZURE_TENANT_ID          = tenant id
AZURE_SUBSCRIPTION_ID    = subscription id
AZURE_RESOURCE_GROUP     = rg-india-market-intel
AZURE_ACR_NAME           = indiamarketintelacr
AZURE_APP_NAME           = india-market-intel-app
SCRAPER_ADMIN_TOKEN      = a strong private token
```

Push to GitHub:

```powershell
git init
git add .
git commit -m "Deploy dashboard scraper app"
git branch -M main
git remote add origin "https://github.com/$githubOrg/$githubRepo.git"
git push -u origin main
```

GitHub Actions will then:

1. Log in to Azure using OIDC.
2. Build the Docker image from `Dockerfile`.
3. Push it to Azure Container Registry.
4. Configure App Service to use that image.
5. Set runtime scraper settings.
6. Restart the app.

After the workflow succeeds, open:

```text
https://<app-name>.azurewebsites.net/
```

### First GitHub Actions Smoke Test

1. Open the deployed URL.
2. Confirm the VAHAN dashboard loads.
3. Switch to Solar DCR.
4. Click `Rebuild Solar`.
5. Enter your `SCRAPER_ADMIN_TOKEN`.
6. Confirm the job succeeds in the log panel.
7. Test `Refresh Solar`.
8. Test `Refresh VAHAN` only when you are ready for a longer Selenium job.

## First Production Checks

1. Open `/api/health`.
2. Open `/` and confirm both dashboards switch.
3. Press `Rebuild Solar`; it should finish quickly.
4. Press `Rebuild VAHAN`; it should rebuild payloads from existing data.
5. Press `Refresh Solar`; it should scrape NISE and rebuild the Solar dashboard.
6. Press `Refresh VAHAN`; expect a much longer Selenium job.

## Operational Notes

- Full VAHAN historical scraping is heavy. Use the default `Refresh VAHAN` button for current/previous month refreshes.
- Keep App Service on a paid tier with Always On enabled for long jobs.
- If a job fails, open `/api/jobs/{job_id}/log` or use the frontend log panel.
- If the persistent workspace gets corrupted, set `RESET_RUNTIME_WORKSPACE=true`, restart once, then remove or set it back to `false`.
- Do not expose scraper buttons without `SCRAPER_ADMIN_TOKEN`.

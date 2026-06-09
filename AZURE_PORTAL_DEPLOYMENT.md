# Azure Portal UI Deployment Guide

Use this when you want to deploy from the Azure UI instead of Azure CLI.

The target architecture is:

```text
GitHub repo
  -> GitHub Actions builds Dockerfile
  -> pushes image to Azure Container Registry
  -> Azure App Service pulls and runs the container
```

The app runs as one custom container:

- `index.html` dashboard switcher
- Flask backend from `app.py`
- Solar scraper
- VAHAN Selenium scraper
- Chromium + ChromeDriver from `Dockerfile`

## 0. Push This Folder To GitHub

In GitHub UI:

1. Create a new repository.
2. Upload/push this folder.
3. Make sure these files exist in the repo:

```text
Dockerfile
app.py
startup.sh
requirements.txt
index.html
solar_dcr_scrape/
vahan_dashboard_project/
.github/workflows/azure-app-service-container.yml
```

## 1. Create Azure Container Registry

In Azure Portal:

1. Search for `Container registries`.
2. Click `Create`.
3. Basics:
   - Subscription: your subscription
   - Resource group: create `rg-india-market-intel`
   - Registry name: choose a globally unique name, for example `indiamarketintelacr`
   - Region: same region as App Service, for example `Central India` or your preferred region
   - SKU: `Basic` is okay to start
4. Click `Review + create`.
5. Click `Create`.

After it is created:

1. Open the Container Registry.
2. Go to `Access keys`.
3. Turn `Admin user` to `Enabled`.

This is the simplest UI path. Later you can replace it with managed identity.

## 2. Create Azure App Service For Container

In Azure Portal:

1. Search for `App Services`.
2. Click `Create`.
3. Choose `Web App`.
4. Basics:
   - Subscription: your subscription
   - Resource group: `rg-india-market-intel`
   - Name: globally unique, for example `india-market-intel-app`
   - Publish: `Container`
   - Operating System: `Linux`
   - Region: same as ACR
5. App Service Plan:
   - Create new plan
   - Pricing tier: use `Premium v3 P1V3` if possible

Why P1V3: VAHAN Selenium jobs need memory/CPU and Always On. You can test cheaper tiers, but do not use Free/Shared for this.

Container tab:

If Azure asks for an image now and your ACR is still empty, use a temporary public image:

```text
mcr.microsoft.com/appsvc/staticsite:latest
```

The GitHub Action will replace this with your real image after the first deployment.

Click:

```text
Review + create -> Create
```

## 3. Configure App Settings In Azure UI

Open your App Service:

```text
App Service -> Settings -> Environment variables
```

Add these app settings:

```text
WEBSITES_ENABLE_APP_SERVICE_STORAGE = true
WEBSITES_PORT = 8000
SCRAPER_ADMIN_TOKEN = choose-a-long-private-token
SCRAPER_WORKSPACE_DIR = /home/site/dashboard-workspace
SCRAPER_RUNTIME_DIR = /home/site/scraper-runtime
CHROME_BIN = /usr/bin/chromium
WEB_CONCURRENCY = 1
GUNICORN_THREADS = 4
GUNICORN_TIMEOUT = 900
VAHAN_DELAY = 0.4
VAHAN_ATTEMPTS = 4
VAHAN_WAIT_SECONDS = 120
VAHAN_PAGE_TIMEOUT = 120
VAHAN_RETRY_SLEEP = 8
```

Click `Apply` or `Save`.

Then go to:

```text
App Service -> Settings -> Configuration -> General settings
```

Set:

```text
Always On = On
```

Save.

## 4. Create GitHub OIDC App Registration In Azure UI

In Azure Portal:

1. Search for `Microsoft Entra ID`.
2. Go to `App registrations`.
3. Click `New registration`.
4. Name: `gh-india-market-intel-deploy`.
5. Supported account types: `Single tenant`.
6. Click `Register`.

Copy these values:

```text
Application (client) ID
Directory (tenant) ID
```

Now add GitHub federation:

1. Inside the app registration, go to `Certificates & secrets`.
2. Open `Federated credentials`.
3. Click `Add credential`.
4. Select `GitHub Actions deploying Azure resources`.
5. Fill:
   - Organization: your GitHub username/org
   - Repository: your repo name
   - Entity type: `Branch`
   - Branch: `main`
   - Name: `github-main`
6. Click `Add`.

## 5. Give The GitHub Identity Azure Permissions

Open the Resource Group:

```text
Resource groups -> rg-india-market-intel -> Access control (IAM)
```

Add role assignment:

```text
Role: Contributor
Assign access to: User, group, or service principal
Members: gh-india-market-intel-deploy
```

Open the Container Registry:

```text
Container registries -> your ACR -> Access control (IAM)
```

Add role assignment:

```text
Role: AcrPush
Assign access to: User, group, or service principal
Members: gh-india-market-intel-deploy
```

## 6. Add GitHub Secrets In GitHub UI

In GitHub:

```text
Repo -> Settings -> Secrets and variables -> Actions -> New repository secret
```

Add:

```text
AZURE_CLIENT_ID = Application/client ID from app registration
AZURE_TENANT_ID = Directory/tenant ID
AZURE_SUBSCRIPTION_ID = your Azure subscription ID
AZURE_RESOURCE_GROUP = rg-india-market-intel
AZURE_ACR_NAME = your ACR name, for example indiamarketintelacr
AZURE_APP_NAME = your App Service name, for example india-market-intel-app
SCRAPER_ADMIN_TOKEN = same token you placed in Azure App Settings
```

## 7. Run GitHub Actions From GitHub UI

In GitHub:

1. Open your repo.
2. Go to `Actions`.
3. Select `Build And Deploy Azure App Service Container`.
4. Click `Run workflow`.
5. Choose branch `main`.
6. Click the green `Run workflow` button.

The workflow will:

1. Login to Azure using OIDC.
2. Build the Docker image from `Dockerfile`.
3. Push it to Azure Container Registry.
4. Configure App Service to use the new image.
5. Set required environment variables.
6. Restart App Service.

## 8. Verify In Azure UI

In Azure Portal:

```text
App Service -> Deployment Center
```

Check deployment status.

Then:

```text
App Service -> Monitoring -> Log stream
```

You should see Gunicorn/container logs.

Open:

```text
https://<your-app-name>.azurewebsites.net/
```

Test:

1. VAHAN dashboard loads.
2. Solar dashboard switch works.
3. Click `Rebuild Solar`.
4. Enter `SCRAPER_ADMIN_TOKEN`.
5. Watch job log panel.
6. Try `Refresh Solar`.
7. Try `Refresh VAHAN` only when you are ready for a longer Selenium scrape.

## 9. If The Site Does Not Start

Check these first:

1. `WEBSITES_PORT` must be `8000`.
2. App Service must be Linux container.
3. App Service log stream should show Gunicorn starting.
4. Container image should point to your ACR image, not the temporary placeholder.
5. ACR admin user must be enabled for this simple UI path.
6. `SCRAPER_ADMIN_TOKEN` should be set.

## 10. Important Production Notes

1. Keep instance count at `1` if you enable scheduled scraping.
2. Do not use Free/Shared tiers for Selenium.
3. Use `Always On`.
4. Do not expose scraper controls without `SCRAPER_ADMIN_TOKEN`.
5. VAHAN may timeout or throttle sometimes; check job logs before assuming code is broken.

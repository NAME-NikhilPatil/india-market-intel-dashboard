# Azure Static Deployment Guide

If you want the deployed app to run the scrapers too, use the App Service custom-container guide instead:

- `AZURE_APP_SERVICE.md`

This file is for the simpler static-only deployment.

This project is a static website now:

- `index.html` is the dashboard switcher.
- `solar_dcr_scrape/solar_dcr_dashboard.html` is the Solar DCR dashboard.
- `vahan_dashboard_project/vahan_dashboard_v19.html` is the VAHAN dashboard.

Do not deploy the full archive folder. The raw datasets, logs, and archive files are useful for rebuilding, but they make the website unnecessarily large.

## Recommended Azure Service

Use Azure Static Web Apps.

Why:

1. The site is plain HTML, CSS, and JavaScript.
2. No server is required.
3. GitHub-based CI/CD is built in.
4. HTTPS and custom domains are straightforward.
5. It leaves room for a future API if you later add authenticated data refreshes.

Azure Blob Storage static website hosting also works, but it is better for simple static hosting without preview environments or GitHub workflow niceties.

## Prepare The Deployable Folder

From this folder:

```powershell
.\prepare_azure_static_site.ps1
```

That creates:

```text
dist/
  index.html
  staticwebapp.config.json
  solar_dcr_scrape/
    solar_dcr_dashboard.html
  vahan_dashboard_project/
    vahan_dashboard_v19.html
```

The current deployable payload is roughly 14 MB, instead of the full 1 GB archive.

## Option A: Deploy With Azure Static Web Apps And GitHub

This is the best long-term path.

1. Create a GitHub repository.
2. Commit the active project files.
3. In the Azure portal, create a new Static Web App.
4. Choose GitHub as the deployment source.
5. Select your repository and branch.
6. Set build details like this:

```text
App location: /
Api location: leave blank
Output location: dist
```

7. After Azure creates the GitHub Actions workflow, edit the generated workflow so it prepares `dist` before deploy.

Example workflow shape:

```yaml
name: Azure Static Web Apps CI/CD

on:
  push:
    branches:
      - main
  pull_request:
    types:
      - opened
      - synchronize
      - reopened
      - closed
    branches:
      - main

jobs:
  build_and_deploy_job:
    if: github.event_name == 'push' || (github.event_name == 'pull_request' && github.event.action != 'closed')
    runs-on: windows-latest
    name: Build and Deploy Job
    steps:
      - uses: actions/checkout@v4

      - name: Prepare static artifact
        shell: pwsh
        run: .\prepare_azure_static_site.ps1

      - name: Build And Deploy
        id: builddeploy
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: upload
          app_location: dist
          api_location: ""
          output_location: ""
          skip_app_build: true

  close_pull_request_job:
    if: github.event_name == 'pull_request' && github.event.action == 'closed'
    runs-on: ubuntu-latest
    name: Close Pull Request Job
    steps:
      - name: Close Pull Request
        id: closepullrequest
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          action: close
```

The key settings are `app_location: dist` and `skip_app_build: true`, because this project does not need npm, Vite, React, or a build compiler.

## Option B: Deploy With Azure CLI

Use this when you want to deploy from your machine first, before setting up GitHub CI/CD.

Install tools:

```powershell
npm install -g @azure/static-web-apps-cli
az login
```

Prepare the deployable folder:

```powershell
.\prepare_azure_static_site.ps1
```

Create the Static Web App in Azure:

```powershell
az group create --name rg-india-market-intel --location centralindia

az staticwebapp create `
  --name india-market-intel `
  --resource-group rg-india-market-intel `
  --location centralindia `
  --source .
```

Then deploy the prepared folder:

```powershell
swa deploy .\dist --env production
```

If the CLI asks for a deployment token, get it from the Azure portal:

```text
Static Web App -> Manage deployment token
```

## Option C: Azure Blob Storage Static Website

Use this only if you want the cheapest/simple-hosting route and do not care about GitHub preview deployments.

```powershell
az group create --name rg-india-market-intel --location centralindia

az storage account create `
  --name indiamarketintelweb `
  --resource-group rg-india-market-intel `
  --location centralindia `
  --sku Standard_LRS `
  --kind StorageV2

az storage blob service-properties update `
  --account-name indiamarketintelweb `
  --static-website `
  --index-document index.html `
  --404-document index.html

.\prepare_azure_static_site.ps1

az storage blob upload-batch `
  --account-name indiamarketintelweb `
  --destination '$web' `
  --source .\dist `
  --overwrite
```

## Refresh Workflow

When either dashboard changes:

1. Regenerate the dashboard HTML.
2. Run:

```powershell
.\prepare_azure_static_site.ps1
```

3. Commit the updated files if using GitHub deployment.
4. Or run `swa deploy .\dist --env production` if using manual CLI deployment.

## Production Checklist

1. Open `/` and verify the VAHAN dashboard loads.
2. Click Solar DCR and verify the charts render.
3. Test direct URLs:
   - `/vahan_dashboard_project/vahan_dashboard_v19.html`
   - `/solar_dcr_scrape/solar_dcr_dashboard.html`
4. Set a custom domain after the first successful deployment.
5. Keep raw data and logs out of the deployed artifact unless you intentionally want public downloads.

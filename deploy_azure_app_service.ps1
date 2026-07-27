param(
  [Parameter(Mandatory = $true)]
  [string]$ResourceGroup,

  [Parameter(Mandatory = $true)]
  [string]$AcrName,

  [Parameter(Mandatory = $true)]
  [string]$AppName,

  [Parameter(Mandatory = $true)]
  [string]$AdminToken,

  [string]$Location = "centralindia",
  [string]$PlanName = "$AppName-plan",
  [string]$ImageRepository = "india-market-intel",
  [string]$ImageTag = "latest",
  [string]$Sku = "P1V3"
)

$ErrorActionPreference = "Stop"

$Image = "$AcrName.azurecr.io/$ImageRepository`:$ImageTag"

az group create --name $ResourceGroup --location $Location | Out-Null

az acr create `
  --resource-group $ResourceGroup `
  --name $AcrName `
  --sku Basic `
  --admin-enabled true | Out-Null

az acr login --name $AcrName | Out-Null

docker build -t $Image .
docker push $Image

az appservice plan create `
  --name $PlanName `
  --resource-group $ResourceGroup `
  --is-linux `
  --sku $Sku | Out-Null

$ExistingApp = az webapp show --name $AppName --resource-group $ResourceGroup 2>$null
if (-not $ExistingApp) {
  az webapp create `
    --resource-group $ResourceGroup `
    --plan $PlanName `
    --name $AppName `
    --deployment-container-image-name $Image | Out-Null
}

$AcrCred = az acr credential show --name $AcrName | ConvertFrom-Json
$AcrUser = $AcrCred.username
$AcrPass = $AcrCred.passwords[0].value

az webapp config container set `
  --name $AppName `
  --resource-group $ResourceGroup `
  --docker-custom-image-name $Image `
  --docker-registry-server-url "https://$AcrName.azurecr.io" `
  --docker-registry-server-user $AcrUser `
  --docker-registry-server-password $AcrPass | Out-Null

az webapp config appsettings set `
  --name $AppName `
  --resource-group $ResourceGroup `
  --settings `
    WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
    WEBSITES_PORT=8000 `
    SCRAPER_ADMIN_TOKEN=$AdminToken `
    SCRAPER_WORKSPACE_DIR=/home/site/dashboard-workspace `
    SCRAPER_RUNTIME_DIR=/home/site/scraper-runtime `
    CHROME_BIN=/usr/bin/chromium `
    WEB_CONCURRENCY=1 `
    GUNICORN_THREADS=4 `
    GUNICORN_TIMEOUT=900 `
    VAHAN_DELAY=0.4 `
    VAHAN_ATTEMPTS=4 `
    VAHAN_WAIT_SECONDS=120 `
    VAHAN_PAGE_TIMEOUT=120 `
    VAHAN_RETRY_SLEEP=8 `
    VAHAN_HEADFUL=true `
    ENABLE_SCRAPER_SCHEDULER=true `
    SOLAR_DAILY_UTC=02:30 `
    VAHAN_DAILY_UTC=03:30 | Out-Null

az webapp config set `
  --name $AppName `
  --resource-group $ResourceGroup `
  --always-on true | Out-Null

az webapp restart --name $AppName --resource-group $ResourceGroup | Out-Null

Write-Host "Deployed $Image"
Write-Host "Open: https://$AppName.azurewebsites.net/"

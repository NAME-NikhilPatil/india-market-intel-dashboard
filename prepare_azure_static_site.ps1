param(
  [string]$OutputPath = "dist"
)

$ErrorActionPreference = "Stop"

$Root = [System.IO.Path]::GetFullPath($PSScriptRoot)
$Dist = [System.IO.Path]::GetFullPath((Join-Path $Root $OutputPath))

if (-not $Dist.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase) -or $Dist -eq $Root) {
  throw "Refusing to prepare output outside the project folder: $Dist"
}

if (Test-Path -LiteralPath $Dist) {
  Remove-Item -LiteralPath $Dist -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist "solar_dcr_scrape") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist "vahan_dashboard_project") | Out-Null

Copy-Item -LiteralPath (Join-Path $Root "index.html") -Destination (Join-Path $Dist "index.html")
Copy-Item -LiteralPath (Join-Path $Root "staticwebapp.config.json") -Destination (Join-Path $Dist "staticwebapp.config.json")
Copy-Item -LiteralPath (Join-Path $Root "solar_dcr_scrape\solar_dcr_dashboard.html") -Destination (Join-Path $Dist "solar_dcr_scrape\solar_dcr_dashboard.html")
Copy-Item -LiteralPath (Join-Path $Root "vahan_dashboard_project\vahan_dashboard_v19.html") -Destination (Join-Path $Dist "vahan_dashboard_project\vahan_dashboard_v19.html")

$TotalBytes = (Get-ChildItem -LiteralPath $Dist -Recurse -File | Measure-Object -Property Length -Sum).Sum
$TotalMb = [Math]::Round($TotalBytes / 1MB, 2)

Write-Host "Prepared Azure static site at: $Dist"
Write-Host "Deployable size: $TotalMb MB"

param(
    [switch]$SkipBuild,
    [string]$GiteeToken = $env:GITEE_TOKEN
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Set-Location $projectRoot

$ver = (Select-String -Path "pyproject.toml" -Pattern 'version\s*=\s*"([^"]+)"' | Select-Object -First 1).Matches.Groups[1].Value
if (-not $ver) { Write-Error "Cannot read version from pyproject.toml"; exit 1 }
$tag = "v$ver"
$file = "package/dist/IRtool-v$ver.zip"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IRtool Release v$ver" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[1/3] Building package ..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File "package/build-with-7z.ps1" -Mode onedir-7z
    if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit 1 }
} else {
    Write-Host ""
    Write-Host "[1/3] Build skipped (--SkipBuild)" -ForegroundColor Yellow
}

if (-not (Test-Path $file)) {
    Write-Error "Build artifact not found: $file"
    exit 1
}
$fileSize = [math]::Round((Get-Item $file).Length / 1MB, 2)
Write-Host "  Artifact: $file ($fileSize MB)" -ForegroundColor Green

function Get-ApiMsg {
    param($errRecord)
    $msg = ""
    if ($errRecord.ErrorDetails -and $errRecord.ErrorDetails.Message) {
        try {
            $json = $errRecord.ErrorDetails.Message | ConvertFrom-Json
            if ($json.message) { $msg = $json.message }
            elseif ($json.messages) { $msg = $json.messages -join ", " }
            else { $msg = $errRecord.ErrorDetails.Message }
        } catch { $msg = $errRecord.ErrorDetails.Message }
    }
    if (-not $msg) { $msg = $errRecord.Exception.Message }
    return $msg
}

Write-Host ""
Write-Host "[2/3] Uploading to GitHub Release ..." -ForegroundColor Yellow

$ghExists = gh release view $tag --repo summerxzp/IRtool 2>$null
if ($ghExists) {
    Write-Host "  GitHub Release $tag already exists, uploading asset ..." -ForegroundColor Gray
    gh release upload $tag $file --repo summerxzp/IRtool --clobber
} else {
    gh release create $tag $file --repo summerxzp/IRtool --title "IRtool $tag" --notes "Automated release build"
}
if ($LASTEXITCODE -ne 0) { Write-Error "GitHub release failed"; exit 1 }
Write-Host "  GitHub Release done" -ForegroundColor Green

Write-Host ""
Write-Host "[3/3] Uploading to Gitee Release ..." -ForegroundColor Yellow

if (-not $GiteeToken) {
    Write-Warning "GITEE_TOKEN not set. Pass -GiteeToken or set env GITEE_TOKEN. Skipping Gitee upload."
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Release complete: GitHub only" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    exit 0
}

$owner = "summerxzp"
$repo = "irtool"

try {
    $tagBody = @{
        access_token = $GiteeToken
        refs         = "refs/heads/master"
        tag_name     = $tag
    }
    Invoke-RestMethod -Uri "https://gitee.com/api/v5/repos/$owner/$repo/tags" -Method Post -Body $tagBody -ContentType "application/x-www-form-urlencoded" -ErrorAction Stop
    Write-Host "  Tag $tag created on Gitee" -ForegroundColor Gray
} catch {
    $errMsg = Get-ApiMsg $_
    Write-Host "  Tag response: $errMsg" -ForegroundColor Gray
    if ($errMsg -match "已经存在" -or $errMsg -match "已存在" -or $errMsg -match "already exist") {
        Write-Host "  Tag $tag already exists, continuing" -ForegroundColor Gray
    } else {
        Write-Error "Failed to create Gitee tag: $errMsg"
        exit 1
    }
}

$releaseId = $null
try {
    Write-Host "  Creating Gitee release for $tag ..." -ForegroundColor Gray
    $body = @{
        access_token     = $GiteeToken
        tag_name         = $tag
        name             = "IRtool $tag"
        body             = "Automated release build"
        target_commitish = "master"
    }
    $resp = Invoke-RestMethod -Uri "https://gitee.com/api/v5/repos/$owner/$repo/releases" -Method Post -Body $body -ContentType "application/x-www-form-urlencoded" -ErrorAction Stop
    $releaseId = $resp.id
    Write-Host "  Gitee release created: $releaseId" -ForegroundColor Gray
} catch {
    $errMsg2 = Get-ApiMsg $_
    Write-Host "  Release response: $errMsg2" -ForegroundColor Gray
    if ($errMsg2 -match "已经存在" -or $errMsg2 -match "已存在" -or $errMsg2 -match "already exist") {
        try {
            $existing = Invoke-RestMethod -Uri "https://gitee.com/api/v5/repos/$owner/$repo/releases/tags/$tag" -Method Get -Body @{ access_token = $GiteeToken } -ErrorAction Stop
            $releaseId = $existing.id
            Write-Host "  Using existing release: $releaseId" -ForegroundColor Gray
        } catch {
            Write-Error "Failed to fetch existing Gitee release: $(Get-ApiMsg $_)"
            exit 1
        }
    } else {
        Write-Error "Failed to create Gitee release: $errMsg2"
        exit 1
    }
}

if (-not $releaseId) {
    Write-Error "Could not obtain Gitee release ID"
    exit 1
}

Write-Host "  Uploading $file ($fileSize MB) to Gitee ..." -ForegroundColor Gray
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $uploadUrl = "https://gitee.com/api/v5/repos/$owner/$repo/releases/$releaseId/attach_files?access_token=$GiteeToken"
    $form = @{ file = Get-Item -Path $file }
    $uploadResp = Invoke-RestMethod -Uri $uploadUrl -Method Post -Form $form -TimeoutSec 600 -ErrorAction Stop
    $stopwatch.Stop()
    Write-Host "  File uploaded: $($uploadResp.name) ($([math]::Round($stopwatch.Elapsed.TotalSeconds,1))s)" -ForegroundColor Green
} catch {
    $stopwatch.Stop()
    $errMsg3 = Get-ApiMsg $_
    if ($errMsg3 -match "已经存在" -or $errMsg3 -match "已存在" -or $errMsg3 -match "already exist") {
        Write-Host "  File already exists, skipping" -ForegroundColor Green
    } else {
        Write-Error "Failed to upload to Gitee: $errMsg3"
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Release complete!" -ForegroundColor Green
Write-Host "  GitHub: https://github.com/summerxzp/IRtool/releases/tag/$tag" -ForegroundColor Cyan
Write-Host "  Gitee:  https://gitee.com/summerxzp/irtool/releases/tag/$tag" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
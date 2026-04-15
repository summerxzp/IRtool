# Create ZIP archive for IRtool
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $here 'dist')

$outputName = 'IRtool-v1.1.1'
$dirPath = $outputName
$zipPath = "$outputName.zip"

Write-Host "Creating ZIP archive..." -ForegroundColor Cyan

# Create logs and config directories if not exist
$logsDir = Join-Path $dirPath 'logs'
$configDir = Join-Path $dirPath 'config'
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

# Clean up old zip
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Host "Removed old ZIP file" -ForegroundColor Yellow
}

# Create temp dir with version folder structure
$tempDir = 'temp_zip'
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

# Copy to temp dir with version folder name
$versionDir = Join-Path $tempDir $outputName
Copy-Item $dirPath $versionDir -Recurse -Force
Write-Host "Copied files to temp directory" -ForegroundColor Cyan

# Create ZIP
Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -Force
Write-Host "Created ZIP archive" -ForegroundColor Cyan

# Clean up
Remove-Item $tempDir -Recurse -Force

# Show result
$zipSize = (Get-Item $zipPath).Length / 1MB
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "ZIP archive created successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Output: $zipPath" -ForegroundColor Yellow
Write-Host "Size: $([math]::Round($zipSize,2)) MB" -ForegroundColor Yellow

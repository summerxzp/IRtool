# Simple build script using root venv
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = Split-Path -Parent $here
Set-Location $here

# Use pyinstaller directly from venv
$pyInstaller = Join-Path $appDir '.venv\Scripts\pyinstaller.exe'
Write-Host "Using PyInstaller: $pyInstaller" -ForegroundColor Green

# Check 7z
$sevenZip = $null
if (Get-Command 7z -ErrorAction SilentlyContinue) {
    $sevenZip = '7z'
} elseif (Test-Path 'D:\Sofware\7-Zip\7z.exe') {
    $sevenZip = 'D:\Sofware\7-Zip\7z.exe'
}

if (-not $sevenZip) {
    Write-Host "7-Zip not found!" -ForegroundColor Red
    exit 1
}
Write-Host "7-Zip found: $sevenZip" -ForegroundColor Green

$appVersion = "1.1.4"
$outputName = "IRtool-v$appVersion"

# Build args
$buildArgs = @(
    '--clean',
    '--noconsole',
    '--name',$outputName,
    '--distpath', (Join-Path $here 'dist'),
    '--workpath', (Join-Path $here 'build'),
    '--specpath', (Join-Path $here 'build'),
    '--paths', $appDir,
    '--manifest', (Join-Path $here 'IRtool.manifest'),
    '--hidden-import','PyQt6.sip',
    '--hidden-import','PyQt6.QtCore',
    '--hidden-import','PyQt6.QtGui',
    '--hidden-import','PyQt6.QtWidgets',
    '--hidden-import','win32service',
    '--hidden-import','win32serviceutil',
    '--hidden-import','win32evtlog',
    '--collect-binaries','pywin32',
    '--collect-binaries','PyQt6',
    '--add-data', "$(Join-Path $appDir 'data\rules.json');data",
    '--add-data', "$(Join-Path $appDir 'tools\autorunsc64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\sigcheck64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\Sysmon64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\sysmon_config.xml');tools",
    '--exclude-module','matplotlib',
    '--exclude-module','numpy',
    '--exclude-module','pandas',
    '--exclude-module','scipy',
    '--exclude-module','PIL',
    '--exclude-module','tkinter',
    '--exclude-module','unittest',
    '--onedir',
    (Join-Path $appDir 'main.py')
)

Write-Host "Building..." -ForegroundColor Cyan
& $pyInstaller @buildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Build successful!" -ForegroundColor Green

# Create 7z SFX
$dirPath = Join-Path $here "dist\$outputName"

# Create logs and config dirs
$logsDir = Join-Path $dirPath "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$configDir = Join-Path $dirPath "config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

$archivePath = Join-Path $here "dist\$outputName.7z"
$sfxPath = Join-Path $here "dist\$outputName-7z.exe"

# Clean old
if (Test-Path $sfxPath) { Remove-Item $sfxPath -Force }
if (Test-Path $archivePath) { Remove-Item $archivePath -Force }

# Create temp dir with structure
$tempDir = Join-Path $here "dist\temp_7z"
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Path $tempDir | Out-Null

$versionDir = Join-Path $tempDir $outputName
Copy-Item $dirPath $versionDir -Recurse -Force

# Create 7z
Push-Location $tempDir
& $sevenZip a -t7z -m0=lzma2 -mx=9 "$archivePath" *
Pop-Location

Remove-Item $tempDir -Recurse -Force

if ($LASTEXITCODE -ne 0) {
    Write-Host "7z compression failed!" -ForegroundColor Red
    exit 1
}

# Combine SFX
$sfxModule = Join-Path (Split-Path $sevenZip) '7z.sfx'
if (-not (Test-Path $sfxModule)) {
    Write-Host "7z.sfx not found!" -ForegroundColor Red
    exit 1
}

$configContent = ";!@Install@!UTF-8!`nTitle=`"IRtool v$appVersion`"`nBeginPrompt=`"Extract and run IRtool?`"`nExtractPath=`"%TEMP%\IRtool-$appVersion-%PID%`"`nOverwriteMode=0`nGUIRunOnce=`"%TEMP%\IRtool-$appVersion-%PID%\$outputName.exe`"`n;!@InstallEnd@!`n"
$configFile = Join-Path $here 'dist\sfx_config.txt'
Set-Content -Path $configFile -Value $configContent -Encoding UTF8

$sfxBytes = [System.IO.File]::ReadAllBytes($sfxModule)
$configBytes = [System.IO.File]::ReadAllBytes($configFile)
$archiveBytes = [System.IO.File]::ReadAllBytes($archivePath)

$outputBytes = New-Object byte[] ($sfxBytes.Length + $configBytes.Length + $archiveBytes.Length)
[System.Array]::Copy($sfxBytes, 0, $outputBytes, 0, $sfxBytes.Length)
[System.Array]::Copy($configBytes, 0, $outputBytes, $sfxBytes.Length, $configBytes.Length)
[System.Array]::Copy($archiveBytes, 0, $outputBytes, $sfxBytes.Length + $configBytes.Length, $archiveBytes.Length)

[System.IO.File]::WriteAllBytes($sfxPath, $outputBytes)

Remove-Item $archivePath
Remove-Item $configFile

$sfxSize = (Get-Item $sfxPath).Length / 1MB
Write-Host "========================================" -ForegroundColor Green
Write-Host "Done! Output: $sfxPath" -ForegroundColor Green
Write-Host "Size: $([math]::Round($sfxSize,2)) MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

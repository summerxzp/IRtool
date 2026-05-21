# Final build script with proper venv setup
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = Split-Path -Parent $here
Set-Location $here

# Cleanup
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# Create fresh venv
$venvPath = Join-Path $here "build-venv"
if (Test-Path $venvPath) { Remove-Item -Recurse -Force $venvPath }
Write-Host "Creating fresh venv..." -ForegroundColor Cyan
D:\Sofware\python3.11.9\python.exe -m venv $venvPath

# Activate and install
$python = Join-Path $venvPath "Scripts\python.exe"
Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $python -m pip install -r (Join-Path $here "requirements-build.txt")

# Find 7z
$sevenZip = $null
if (Get-Command 7z -ErrorAction SilentlyContinue) {
    $sevenZip = "7z"
} elseif (Test-Path "D:\Sofware\7-Zip\7z.exe") {
    $sevenZip = "D:\Sofware\7-Zip\7z.exe"
}
if (-not $sevenZip) {
    Write-Host "7z not found!" -ForegroundColor Red; exit 1
}
Write-Host "Found 7z: $sevenZip" -ForegroundColor Green

$appVersion = "1.1.4"
$outputName = "IRtool-v$appVersion"

# Build args
$buildArgs = @(
    "-m","PyInstaller",
    "--clean",
    "--noconsole",
    "--name", $outputName,
    "--distpath", (Join-Path $here "dist"),
    "--workpath", (Join-Path $here "build"),
    "--specpath", (Join-Path $here "build"),
    "--paths", $appDir,
    "--manifest", (Join-Path $here "IRtool.manifest"),
    "--hidden-import","PyQt6.sip",
    "--hidden-import","PyQt6.QtCore",
    "--hidden-import","PyQt6.QtGui",
    "--hidden-import","PyQt6.QtWidgets",
    "--hidden-import","win32service",
    "--hidden-import","win32serviceutil",
    "--hidden-import","win32evtlog",
    "--collect-binaries","pywin32",
    "--collect-binaries","PyQt6",
    "--add-data", "$(Join-Path $appDir 'data\rules.json');data",
    "--add-data", "$(Join-Path $appDir 'tools\autorunsc64.exe');tools",
    "--add-data", "$(Join-Path $appDir 'tools\sigcheck64.exe');tools",
    "--add-data", "$(Join-Path $appDir 'tools\Sysmon64.exe');tools",
    "--add-data", "$(Join-Path $appDir 'tools\sysmon_config.xml');tools",
    "--exclude-module","matplotlib",
    "--exclude-module","numpy",
    "--exclude-module","pandas",
    "--exclude-module","scipy",
    "--exclude-module","PIL",
    "--exclude-module","tkinter",
    "--exclude-module","unittest",
    "--onedir",
    (Join-Path $appDir "main.py")
)

Write-Host "Building with PyInstaller..." -ForegroundColor Cyan
& $python @buildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Build successful!" -ForegroundColor Green

# Create 7z
$dirPath = Join-Path $here "dist\$outputName"
$logsDir = Join-Path $dirPath "logs"
$configDir = Join-Path $dirPath "config"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

$archivePath = Join-Path $here "dist\$outputName.7z"
$sfxPath = Join-Path $here "dist\$outputName-7z.exe"

# Clean old
if (Test-Path $sfxPath) { Remove-Item $sfxPath -Force }
if (Test-Path $archivePath) { Remove-Item $archivePath -Force }

# Temp dir for structure
$tempDir = Join-Path $here "dist\temp_7z"
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

$versionDir = Join-Path $tempDir $outputName
Copy-Item $dirPath $versionDir -Recurse -Force

# Make 7z
Push-Location $tempDir
& $sevenZip a -t7z -m0=lzma2 -mx=9 "$archivePath" *
Pop-Location
Remove-Item $tempDir -Recurse -Force

if ($LASTEXITCODE -ne 0) {
    Write-Host "Compression failed!" -ForegroundColor Red; exit 1
}

# Create SFX
$sfxModule = Join-Path (Split-Path $sevenZip) "7z.sfx"
if (-not (Test-Path $sfxModule)) {
    Write-Host "7z.sfx missing!" -ForegroundColor Red; exit 1
}

$configContent = ";!@Install@!UTF-8!`nTitle=`"IRtool v$appVersion`"`nBeginPrompt=`"Extract and run IRtool?`"`nExtractPath=`"%TEMP%\IRtool-$appVersion-%PID%`"`nOverwriteMode=0`nGUIRunOnce=`"%TEMP%\IRtool-$appVersion-%PID%\$outputName.exe`"`n;!@InstallEnd@!`n"
$configFile = Join-Path $here "dist\sfx_config.txt"
Set-Content -Path $configFile -Value $configContent -Encoding UTF8

$sfxBytes = [IO.File]::ReadAllBytes($sfxModule)
$configBytes = [IO.File]::ReadAllBytes($configFile)
$archiveBytes = [IO.File]::ReadAllBytes($archivePath)

$outputBytes = New-Object byte[] ($sfxBytes.Length + $configBytes.Length + $archiveBytes.Length)
[Array]::Copy($sfxBytes, 0, $outputBytes, 0, $sfxBytes.Length)
[Array]::Copy($configBytes, 0, $outputBytes, $sfxBytes.Length, $configBytes.Length)
[Array]::Copy($archiveBytes, 0, $outputBytes, $sfxBytes.Length + $configBytes.Length, $archiveBytes.Length)

[IO.File]::WriteAllBytes($sfxPath, $outputBytes)

Remove-Item $archivePath, $configFile

$sfxSize = (Get-Item $sfxPath).Length / 1MB
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "All done! Output: $sfxPath" -ForegroundColor Green
Write-Host "Size: $([Math]::Round($sfxSize, 2)) MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

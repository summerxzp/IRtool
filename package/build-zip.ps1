# IRtool Release Build Script
# Build Type: onedir + zip
# Version: 1.1.1

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

# Use parent directory (project root) as app directory
$appDir = Split-Path -Parent $here

# Version info (must match core/constants.py)
$appVersion = "1.1.1"
$buildType = "release"
$buildDate = "2026-04-15"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IRtool Release Build (ZIP)" -ForegroundColor Cyan
Write-Host "  Version: $appVersion ($buildType)" -ForegroundColor Cyan
Write-Host "  Date: $buildDate" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Use system Python directly (venv has issues in this environment)
$python = 'python'
Write-Host "Using system Python: $python" -ForegroundColor Yellow
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $python -m pip install -q -r (Join-Path $here 'requirements-build.txt')

# Get PyQt6 Qt6 bin path for DLLs
$qt6BinPath = & $python -c "import PyQt6; import os; print(os.path.join(os.path.dirname(PyQt6.__file__), 'Qt6', 'bin'))"
Write-Host "PyQt6 Qt6 bin path: $qt6BinPath" -ForegroundColor Cyan

Write-Host "App directory: $appDir" -ForegroundColor Cyan

# Output name with version
$outputName = "IRtool-v$appVersion"
$buildName = $outputName

# Base build args
$buildArgs = @(
    '-m','PyInstaller',
    '--clean',
    '--noconsole',
    '--name',$buildName,
    '--distpath', (Join-Path $here 'dist'),
    '--workpath', (Join-Path $here 'build'),
    '--specpath', (Join-Path $here 'build'),
    '--paths', $appDir,
    '--manifest', (Join-Path $here 'IRtool.manifest'),
    '--hidden-import','PyQt6.sip',
    '--hidden-import','PyQt6.QtCore',
    '--hidden-import','PyQt6.QtGui',
    '--hidden-import','PyQt6.QtWidgets',
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
    '--exclude-module','Pillow',
    '--exclude-module','unittest',
    '--exclude-module','pydoc',
    '--exclude-module','pdb',
    '--exclude-module','doctest',
    '--exclude-module','lib2to3',
    '--exclude-module','tkinter',
    '--exclude-module','email.mime',
    '--exclude-module','http.server',
    '--exclude-module','xmlrpc',
    '--exclude-module','html',
    '--exclude-module','_pytest',
    '--exclude-module','pytest',
    '--exclude-module','pytestqt',
    '--exclude-module','PyQt6.Qt3DAnimation',
    '--exclude-module','PyQt6.Qt3DCore',
    '--exclude-module','PyQt6.Qt3DExtras',
    '--exclude-module','PyQt6.Qt3DInput',
    '--exclude-module','PyQt6.Qt3DLogic',
    '--exclude-module','PyQt6.Qt3DRender',
    '--exclude-module','PyQt6.QtBluetooth',
    '--exclude-module','PyQt6.QtCharts',
    '--exclude-module','PyQt6.QtConcurrent',
    '--exclude-module','PyQt6.QtDataVisualization',
    '--exclude-module','PyQt6.QtDesigner',
    '--exclude-module','PyQt6.QtHelp',
    '--exclude-module','PyQt6.QtLocation',
    '--exclude-module','PyQt6.QtMultimedia',
    '--exclude-module','PyQt6.QtMultimediaWidgets',
    '--exclude-module','PyQt6.QtNetworkAuth',
    '--exclude-module','PyQt6.QtNfc',
    '--exclude-module','PyQt6.QtOpenGL',
    '--exclude-module','PyQt6.QtOpenGLWidgets',
    '--exclude-module','PyQt6.QtPdf',
    '--exclude-module','PyQt6.QtPdfWidgets',
    '--exclude-module','PyQt6.QtPositioning',
    '--exclude-module','PyQt6.QtPrintSupport',
    '--exclude-module','PyQt6.QtQml',
    '--exclude-module','PyQt6.QtQuick',
    '--exclude-module','PyQt6.QtQuick3D',
    '--exclude-module','PyQt6.QtQuickWidgets',
    '--exclude-module','PyQt6.QtRemoteObjects',
    '--exclude-module','PyQt6.QtScxml',
    '--exclude-module','PyQt6.QtSensors',
    '--exclude-module','PyQt6.QtSerialPort',
    '--exclude-module','PyQt6.QtSpatialAudio',
    '--exclude-module','PyQt6.QtSql',
    '--exclude-module','PyQt6.QtStateMachine',
    '--exclude-module','PyQt6.QtSvg',
    '--exclude-module','PyQt6.QtSvgWidgets',
    '--exclude-module','PyQt6.QtTest',
    '--exclude-module','PyQt6.QtTextToSpeech',
    '--exclude-module','PyQt6.QtWebChannel',
    '--exclude-module','PyQt6.QtWebEngineCore',
    '--exclude-module','PyQt6.QtWebEngineWidgets',
    '--exclude-module','PyQt6.QtWebSockets',
    '--exclude-module','PyQt6.QtXml',
    '--exclude-module','PyQt6.QtXmlPatterns'
)

# onedir mode
$buildArgs += '--onedir'
Write-Host "Mode: onedir (directory)" -ForegroundColor Green

# Entry - use main.py from project root
$buildArgs += (Join-Path $appDir 'main.py')

Write-Host ""
Write-Host "Building..." -ForegroundColor Cyan
# Set environment variable to auto-confirm PyInstaller cleanup
$env:PYINSTALLER_CLEANUP_CONFIRM = 'yes'
& $python @buildArgs --noconfirm

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Build Success!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green

    $dirPath = Join-Path $here "dist\$outputName"

    Write-Host ""
    Write-Host "Creating ZIP archive..." -ForegroundColor Cyan

    # Create logs and config directories inside the build
    $logsDir = Join-Path $dirPath "logs"
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    $configDir = Join-Path $dirPath "config"
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null

    # Paths for zip creation
    $zipPath = Join-Path $here "dist\$outputName.zip"

    # Clean up old files
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    }

    # Create a temp directory with the correct structure (IRtool-v1.1.1 folder)
    $tempDir = Join-Path $here "dist\temp_zip"
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    
    # Copy build output to temp dir with version folder name
    $versionDir = Join-Path $tempDir $outputName
    Copy-Item $dirPath $versionDir -Recurse -Force

    # Create ZIP archive using PowerShell Compress-Archive
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -Force
    
    # Clean up temp dir
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

    if (Test-Path $zipPath) {
        $zipSize = (Get-Item $zipPath).Length / 1MB
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "ZIP archive created!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "Output: $zipPath" -ForegroundColor Yellow
        Write-Host "Size: $([math]::Round($zipSize,2)) MB" -ForegroundColor Yellow
        Write-Host "Type: ZIP archive (extract to use)" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Usage: Extract and run $outputName.exe" -ForegroundColor White
    } else {
        Write-Host "Failed to create ZIP archive" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Release Build Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Build Failed!" -ForegroundColor Red
    exit 1
}

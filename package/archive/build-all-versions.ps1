# Build three versions: onefile, onedir, onedir+zip
param()

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $scriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building three versions" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Setup venv
$venv = Join-Path $scriptDir '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $venv
}
& $python -m pip install -q -r (Join-Path $scriptDir 'requirements-build.txt')

# Common PyInstaller arguments
$commonArgs = @(
    '-m','PyInstaller',
    '--clean',
    '--noconsole',
    '--distpath', (Join-Path $scriptDir 'dist'),
    '--workpath', (Join-Path $scriptDir 'build'),
    '--specpath', (Join-Path $scriptDir 'build'),
    '--paths', $rootDir,
    '--hidden-import','PyQt6.sip',
    '--hidden-import','PyQt6.QtCore',
    '--hidden-import','PyQt6.QtGui',
    '--hidden-import','PyQt6.QtWidgets',
    '--collect-binaries','PyQt6',
    '--add-data', "$(Join-Path $rootDir 'data\rules.json');data",
    '--add-data', "$(Join-Path $rootDir 'tools\autorunsc64.exe');tools",
    '--add-data', "$(Join-Path $rootDir 'tools\sigcheck64.exe');tools",
    '--exclude-module','matplotlib','--exclude-module','numpy','--exclude-module','pandas',
    '--exclude-module','scipy','--exclude-module','PIL','--exclude-module','Pillow',
    '--exclude-module','unittest','--exclude-module','pydoc','--exclude-module','pdb',
    '--exclude-module','doctest','--exclude-module','lib2to3','--exclude-module','tkinter',
    '--exclude-module','email.mime','--exclude-module','http.server','--exclude-module','xmlrpc',
    '--exclude-module','html','--exclude-module','_pytest','--exclude-module','pytest',
    '--exclude-module','PyQt6.Qt3DAnimation','--exclude-module','PyQt6.Qt3DCore',
    '--exclude-module','PyQt6.Qt3DExtras','--exclude-module','PyQt6.Qt3DInput',
    '--exclude-module','PyQt6.Qt3DLogic','--exclude-module','PyQt6.Qt3DRender',
    '--exclude-module','PyQt6.QtBluetooth','--exclude-module','PyQt6.QtCharts',
    '--exclude-module','PyQt6.QtConcurrent','--exclude-module','PyQt6.QtDataVisualization',
    '--exclude-module','PyQt6.QtDesigner','--exclude-module','PyQt6.QtHelp',
    '--exclude-module','PyQt6.QtLocation','--exclude-module','PyQt6.QtMultimedia',
    '--exclude-module','PyQt6.QtMultimediaWidgets','--exclude-module','PyQt6.QtNetworkAuth',
    '--exclude-module','PyQt6.QtNfc','--exclude-module','PyQt6.QtOpenGL',
    '--exclude-module','PyQt6.QtOpenGLWidgets','--exclude-module','PyQt6.QtPdf',
    '--exclude-module','PyQt6.QtPdfWidgets','--exclude-module','PyQt6.QtPositioning',
    '--exclude-module','PyQt6.QtPrintSupport','--exclude-module','PyQt6.QtQml',
    '--exclude-module','PyQt6.QtQuick','--exclude-module','PyQt6.QtQuick3D',
    '--exclude-module','PyQt6.QtQuickWidgets','--exclude-module','PyQt6.QtRemoteObjects',
    '--exclude-module','PyQt6.QtScxml','--exclude-module','PyQt6.QtSensors',
    '--exclude-module','PyQt6.QtSerialPort','--exclude-module','PyQt6.QtSpatialAudio',
    '--exclude-module','PyQt6.QtSql','--exclude-module','PyQt6.QtStateMachine',
    '--exclude-module','PyQt6.QtSvg','--exclude-module','PyQt6.QtSvgWidgets',
    '--exclude-module','PyQt6.QtTest','--exclude-module','PyQt6.QtTextToSpeech',
    '--exclude-module','PyQt6.QtWebChannel','--exclude-module','PyQt6.QtWebEngineCore',
    '--exclude-module','PyQt6.QtWebEngineWidgets','--exclude-module','PyQt6.QtWebSockets',
    '--exclude-module','PyQt6.QtXml','--exclude-module','PyQt6.QtXmlPatterns'
)

# ========== Version 1: onefile ==========
Write-Host "[1/3] Building onefile version..." -ForegroundColor Green
$onefileArgs = $commonArgs + @('--name','IRtool-onefile','--onefile',(Join-Path $rootDir 'main.py'))
& $python @onefileArgs

# ========== Version 2: onedir ==========
Write-Host "" 
Write-Host "[2/3] Building onedir version..." -ForegroundColor Green
$onedirArgs = $commonArgs + @('--name','IRtool-onedir','--onedir',(Join-Path $rootDir 'main.py'))
& $python @onedirArgs

# ========== Version 3: onedir + zip ==========
Write-Host ""
Write-Host "[3/3] Building onedir-zip version..." -ForegroundColor Green
$onedirZipArgs = $commonArgs + @('--name','IRtool-onedir-zip','--onedir',(Join-Path $rootDir 'main.py'))
& $python @onedirZipArgs

# Compress onedir-zip version
Write-Host ""
Write-Host "Compressing onedir-zip version..." -ForegroundColor Yellow
$zipSource = Join-Path $scriptDir 'dist\sectool-onedir-zip'
$zipTarget = Join-Path $scriptDir 'dist\sectool-onedir-zip.zip'
Compress-Archive -Path "$zipSource\*" -DestinationPath "$zipTarget" -Force

# ========== Output comparison ==========
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Complete! Size Comparison:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$distDir = Join-Path $scriptDir 'dist'

# onefile
$onefileSize = (Get-Item "$distDir\sectool-onefile.exe" -ErrorAction SilentlyContinue).Length
if ($onefileSize) {
    Write-Host ("onefile:     {0:N2} MB (single file)" -f ($onefileSize / 1MB)) -ForegroundColor White
}

# onedir
$onedirExe = Get-Item "$distDir\IRtool-onedir\IRtool-onedir.exe" -ErrorAction SilentlyContinue
if ($onedirExe) {
    $onedirSize = (Get-ChildItem "$distDir\IRtool-onedir" -Recurse | Measure-Object -Property Length -Sum).Sum
    Write-Host ("onedir:      {0:N2} MB (folder)" -f ($onedirSize / 1MB)) -ForegroundColor White
}

# onedir-zip
$zipFile = Get-Item $zipTarget -ErrorAction SilentlyContinue
if ($zipFile) {
    Write-Host ("onedir+zip:  {0:N2} MB (compressed)" -f ($zipFile.Length / 1MB)) -ForegroundColor White
}

Write-Host ""
Write-Host "Notes:" -ForegroundColor Yellow
Write-Host "- onefile:    Single file, slower startup, easy to distribute" -ForegroundColor Gray
Write-Host "- onedir:     Folder, faster startup, scattered files" -ForegroundColor Gray
Write-Host "- onedir+zip: Compressed, needs extraction before use" -ForegroundColor Gray
Write-Host ""
Write-Host "Output directory:" -ForegroundColor Green
Write-Host $distDir -ForegroundColor Green

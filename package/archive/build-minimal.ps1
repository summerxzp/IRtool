param(
    [ValidateSet('onefile','onedir')] [string]$Mode = 'onefile'
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$appDir = Join-Path $here 'app'

# Create venv for build isolation
$venv = Join-Path $here '.venv'
if (-not (Test-Path $venv)) {
    python -m venv $venv
}

$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install -U pip
& $python -m pip install -r (Join-Path $here 'requirements-build.txt')

# Get PyQt6 Qt6 bin path for DLLs
$qt6BinPath = & $python -c "import PyQt6; import os; print(os.path.join(os.path.dirname(PyQt6.__file__), 'Qt6', 'bin'))"
Write-Host "PyQt6 Qt6 bin path: $qt6BinPath" -ForegroundColor Cyan

# Optional UPX (put upx.exe under ./upx)
$upxDir = Join-Path $here 'upx'
$useUpx = Test-Path (Join-Path $upxDir 'upx.exe')

# Build args - 极致精简模式
$args = @(
    '-m','PyInstaller',
    '--clean',
    '--noconsole',
    '--name','IRtool-minimal',
    '--distpath', (Join-Path $here 'dist'),
    '--workpath', (Join-Path $here 'build'),
    '--specpath', (Join-Path $here 'build'),
    '--paths', $appDir,
    '--hidden-import','PyQt6.sip',
    '--hidden-import','PyQt6.QtCore',
    '--hidden-import','PyQt6.QtGui',
    '--hidden-import','PyQt6.QtWidgets',
    '--collect-binaries','PyQt6',
    '--add-data', "$(Join-Path $appDir 'data\rules.json');data",
    '--add-data', "$(Join-Path $appDir 'tools\autorunsc64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\sigcheck64.exe');tools",
    # 移除所有不需要的Python标准库模块
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
    # 移除PyQt6不需要的模块
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

if ($Mode -eq 'onefile') {
    $args += '--onefile'
} else {
    $args += '--onedir'
}

if ($useUpx) {
    $args += @('--upx-dir', $upxDir)
}

# Entry
$args += 'app\main.py'

Write-Host "Building with args: $args" -ForegroundColor Cyan
& $python @args

Write-Host "Build finished. Output: $here\dist" -ForegroundColor Green
Write-Host ""
Write-Host "Expected size: ~30-50MB (with UPX) or ~50-80MB (without UPX)" -ForegroundColor Yellow

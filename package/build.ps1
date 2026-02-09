param(
    [ValidateSet('onefile','onedir')] [string]$Mode = 'onefile',
    [ValidateSet('slim','safe')] [string]$Preset = 'slim'
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

# Create venv for build isolation
$venv = Join-Path $here '.venv'
if (-not (Test-Path $venv)) {
    python -m venv $venv
}

$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install -U pip
& $python -m pip install -r (Join-Path $here 'requirements-build.txt')

# Optional UPX (put upx.exe under ./upx)
$upxDir = Join-Path $here 'upx'
$useUpx = Test-Path (Join-Path $upxDir 'upx.exe')

# Build args
$args = @(
    '-m','PyInstaller',
    '--clean',
    '--noconsole',
    '--name','sectool',
    '--distpath', (Join-Path $here 'dist'),
    '--workpath', (Join-Path $here 'build'),
    '--specpath', (Join-Path $here 'build'),
    '--paths', 'app',
    '--add-data', 'app\\data\\rules.json;data',
    '--add-data', 'app\\tools\\autorunsc64.exe;tools',
    '--add-data', 'app\\tools\\sigcheck64.exe;tools'
)

if ($Mode -eq 'onefile') {
    $args += '--onefile'
} else {
    $args += '--onedir'
}

if ($useUpx) {
    $args += @('--upx-dir', $upxDir)
}

if ($Preset -eq 'slim') {
    $exclude = @(
        'pytest',
        'pytestqt',
        'PyQt6.Qt3DAnimation',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DExtras',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic',
        'PyQt6.Qt3DRender',
        'PyQt6.QtBluetooth',
        'PyQt6.QtCharts',
        'PyQt6.QtConcurrent',
        'PyQt6.QtDataVisualization',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtLocation',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNetworkAuth',
        'PyQt6.QtNfc',
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
        'PyQt6.QtPositioning',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtQuick3D',
        'PyQt6.QtQuickWidgets',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtScxml',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSpatialAudio',
        'PyQt6.QtSql',
        'PyQt6.QtStateMachine',
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        'PyQt6.QtTest',
        'PyQt6.QtTextToSpeech',
        'PyQt6.QtWebChannel',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebSockets',
        'PyQt6.QtXml',
        'PyQt6.QtXmlPatterns'
    )

    foreach ($m in $exclude) {
        $args += @('--exclude-module', $m)
    }
}

# Entry
$args += 'app\\main.py'

& $python @args

Write-Host "Build finished. Output: $here\\dist"

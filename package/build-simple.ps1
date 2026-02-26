# IRtool Simple Build Script (使用当前环境Python)
# Build Type: onedir + 7z SFX

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$appDir = Split-Path -Parent $here

$appVersion = "1.0.0"
$outputName = "IRtool-v$appVersion"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IRtool Build (PyQt6 6.10.2)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 使用当前 python
$python = "python"

# 安装依赖
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $python -m pip install -q PyQt6==6.10.2 PyQt6-Qt6==6.10.2 PyQt6_sip==13.11.0 psutil==5.9.7 pyzipper==0.3.6 requests==2.31.0 pyinstaller==6.3.0

# 获取 Qt 路径
$qt6BinPath = & $python -c "import PyQt6; import os; print(os.path.join(os.path.dirname(PyQt6.__file__), 'Qt6', 'bin'))"
Write-Host "PyQt6 Qt6 bin path: $qt6BinPath" -ForegroundColor Cyan

# 构建
Write-Host "Building..." -ForegroundColor Cyan
& $python -m PyInstaller `
    --clean `
    --noconsole `
    --name $outputName `
    --distpath (Join-Path $here 'dist') `
    --workpath (Join-Path $here 'build') `
    --specpath (Join-Path $here 'build') `
    --paths $appDir `
    --manifest (Join-Path $here 'IRtool.manifest') `
    --hidden-import PyQt6.sip `
    --hidden-import PyQt6.QtCore `
    --hidden-import PyQt6.QtGui `
    --hidden-import PyQt6.QtWidgets `
    --collect-binaries PyQt6 `
    --add-data (Join-Path $appDir 'data\rules.json')+';data' `
    --add-data (Join-Path $appDir 'tools\autorunsc64.exe')+';tools' `
    --add-data (Join-Path $appDir 'tools\sigcheck64.exe')+';tools' `
    --exclude-module matplotlib `
    --exclude-module numpy `
    --exclude-module pandas `
    --exclude-module scipy `
    --exclude-module PIL `
    --exclude-module Pillow `
    --exclude-module unittest `
    --exclude-module pydoc `
    --exclude-module pdb `
    --exclude-module doctest `
    --exclude-module lib2to3 `
    --exclude-module tkinter `
    --exclude-module email.mime `
    --exclude-module http.server `
    --exclude-module xmlrpc `
    --exclude-module html `
    --exclude-module _pytest `
    --exclude-module pytest `
    --exclude-module pytestqt `
    --exclude-module PyQt6.Qt3DAnimation `
    --exclude-module PyQt6.Qt3DCore `
    --exclude-module PyQt6.Qt3DExtras `
    --exclude-module PyQt6.Qt3DInput `
    --exclude-module PyQt6.Qt3DLogic `
    --exclude-module PyQt6.Qt3DRender `
    --exclude-module PyQt6.QtBluetooth `
    --exclude-module PyQt6.QtCharts `
    --exclude-module PyQt6.QtConcurrent `
    --exclude-module PyQt6.QtDataVisualization `
    --exclude-module PyQt6.QtDesigner `
    --exclude-module PyQt6.QtHelp `
    --exclude-module PyQt6.QtLocation `
    --exclude-module PyQt6.QtMultimedia `
    --exclude-module PyQt6.QtMultimediaWidgets `
    --exclude-module PyQt6.QtNetworkAuth `
    --exclude-module PyQt6.QtNfc `
    --exclude-module PyQt6.QtOpenGL `
    --exclude-module PyQt6.QtOpenGLWidgets `
    --exclude-module PyQt6.QtPdf `
    --exclude-module PyQt6.QtPdfWidgets `
    --exclude-module PyQt6.QtPositioning `
    --exclude-module PyQt6.QtPrintSupport `
    --exclude-module PyQt6.QtQml `
    --exclude-module PyQt6.QtQuick `
    --exclude-module PyQt6.QtQuick3D `
    --exclude-module PyQt6.QtQuickWidgets `
    --exclude-module PyQt6.QtRemoteObjects `
    --exclude-module PyQt6.QtScxml `
    --exclude-module PyQt6.QtSensors `
    --exclude-module PyQt6.QtSerialPort `
    --exclude-module PyQt6.QtSpatialAudio `
    --exclude-module PyQt6.QtSql `
    --exclude-module PyQt6.QtStateMachine `
    --exclude-module PyQt6.QtSvg `
    --exclude-module PyQt6.QtSvgWidgets `
    --exclude-module PyQt6.QtTest `
    --exclude-module PyQt6.QtTextToSpeech `
    --exclude-module PyQt6.QtWebChannel `
    --exclude-module PyQt6.QtWebEngineCore `
    --exclude-module PyQt6.QtWebEngineWidgets `
    --exclude-module PyQt6.QtWebSockets `
    --exclude-module PyQt6.QtXml `
    --exclude-module PyQt6.QtXmlPatterns `
    --onedir `
    (Join-Path $appDir 'main.py')

if ($LASTEXITCODE -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Build Success!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    # 创建 7z 自解压包
    $sevenZip = 'C:\Program Files\7-Zip\7z.exe'
    $dirPath = Join-Path $here "dist\$outputName"
    
    if (Test-Path $sevenZip) {
        Write-Host "Creating 7z self-extracting archive..." -ForegroundColor Cyan
        
        $archivePath = Join-Path $here "dist\$outputName.7z"
        $sfxPath = Join-Path $here "dist\$outputName-7z.exe"
        
        if (Test-Path $sfxPath) { Remove-Item $sfxPath -Force }
        if (Test-Path $archivePath) { Remove-Item $archivePath -Force }
        
        Push-Location $dirPath
        & $sevenZip a -t7z -m0=lzma2 -mx=9 "$archivePath" *
        Pop-Location
        
        if ($LASTEXITCODE -eq 0) {
            $sfxModule = Join-Path (Split-Path $sevenZip) '7z.sfx'
            if (Test-Path $sfxModule) {
                $sfxBytes = [System.IO.File]::ReadAllBytes($sfxModule)
                $archiveBytes = [System.IO.File]::ReadAllBytes($archivePath)
                
                $configContent = ";!@Install@!UTF-8!`nTitle=`"IRtool v$appVersion`"`nExtractPath=`"%TEMP%\IRtool-$appVersion-%PID%`"`nGUIRunOnce=`"%TEMP%\IRtool-$appVersion-%PID%\$outputName.exe`"`n;!@InstallEnd@!`n"
                $configBytes = [System.Text.Encoding]::UTF8.GetBytes($configContent)
                
                $outputBytes = New-Object byte[] ($sfxBytes.Length + $configBytes.Length + $archiveBytes.Length)
                [System.Array]::Copy($sfxBytes, 0, $outputBytes, 0, $sfxBytes.Length)
                [System.Array]::Copy($configBytes, 0, $outputBytes, $sfxBytes.Length, $configBytes.Length)
                [System.Array]::Copy($archiveBytes, 0, $outputBytes, $sfxBytes.Length + $configBytes.Length, $archiveBytes.Length)
                
                [System.IO.File]::WriteAllBytes($sfxPath, $outputBytes)
                Remove-Item $archivePath -ErrorAction SilentlyContinue
                
                $sfxSize = (Get-Item $sfxPath).Length / 1MB
                Write-Host "Self-extracting archive created!" -ForegroundColor Green
                Write-Host "Output: $sfxPath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($sfxSize,2)) MB" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "Build Failed!" -ForegroundColor Red
    exit 1
}

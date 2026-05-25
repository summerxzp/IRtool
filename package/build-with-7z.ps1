# IRtool Release Build Script
# Build Type: onedir + 7z SFX (self-extracting)
# Version: auto-detected from pyproject.toml

param(
    [ValidateSet('onedir','onedir-7z')] [string]$Mode = 'onedir-7z'
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$appDir = Split-Path -Parent $here

$pyprojectPath = Join-Path $appDir 'pyproject.toml'
$appVersion = (Select-String -Path $pyprojectPath -Pattern 'version\s*=\s*"([^"]+)"' | Select-Object -First 1).Matches.Groups[1].Value
if (-not $appVersion) { $appVersion = "0.0.0" }
$buildType = "release"
$buildDate = (Get-Date -Format "yyyy-MM-dd")

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IRtool Release Build" -ForegroundColor Cyan
Write-Host "  Version: $appVersion ($buildType)" -ForegroundColor Cyan
Write-Host "  Date: $buildDate" -ForegroundColor Cyan
Write-Host "  Mode: $Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$sevenZip = $null
if ($Mode -eq 'onedir-7z') {
    $cmd = Get-Command 7z -ErrorAction SilentlyContinue
    if ($cmd) {
        $sevenZip = $cmd.Source
    } elseif (Test-Path 'C:\Program Files\7-Zip\7z.exe') {
        $sevenZip = 'C:\Program Files\7-Zip\7z.exe'
    } elseif (Test-Path 'C:\Program Files (x86)\7-Zip\7z.exe') {
        $sevenZip = 'C:\Program Files (x86)\7-Zip\7z.exe'
    } elseif (Test-Path 'D:\Sofware\7-Zip\7z.exe') {
        $sevenZip = 'D:\Sofware\7-Zip\7z.exe'
    }

    if (-not $sevenZip) {
        Write-Host "7-Zip not found. Please install 7-Zip or use onedir mode." -ForegroundColor Red
        Write-Host "Download: https://www.7-zip.org/" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "7-Zip found: $sevenZip" -ForegroundColor Green
}

$venv = Join-Path $here '.venv'
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    $pythonExe = $null
    foreach ($candidate in @('python', 'python3', 'python3.11')) {
        try { $pythonExe = (Get-Command $candidate -ErrorAction Stop).Source; break } catch {}
    }
    if (-not $pythonExe) {
        Write-Host "Python not found. Please install Python 3.11+ and add to PATH." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using system Python: $pythonExe" -ForegroundColor Yellow
    & $pythonExe -m venv $venv
}

$python = Join-Path $venv 'Scripts\python.exe'
Write-Host "Using Python: $python" -ForegroundColor Yellow
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $python -m pip install --upgrade -r (Join-Path $here 'requirements-build.txt')

$qt6BinPath = & $python -c "import PyQt6; import os; print(os.path.join(os.path.dirname(PyQt6.__file__), 'Qt6', 'bin'))"
Write-Host "PyQt6 Qt6 bin path: $qt6BinPath" -ForegroundColor Cyan

Write-Host "Pre-generating SVG icon files..." -ForegroundColor Yellow
$env:PYTHONPATH = $appDir
& $python -c "from ui.ui_style import ensure_check_svg, ensure_close_svg, ensure_expand_svg, ensure_question_svg; ensure_check_svg(); ensure_close_svg(); ensure_expand_svg(); ensure_question_svg()"
Remove-Item Env:\PYTHONPATH

Write-Host "App directory: $appDir" -ForegroundColor Cyan

$outputName = "IRtool-v$appVersion"
$buildName = $outputName

$buildArgs = @(
    '-m','PyInstaller',
    '--clean',
    '--noconsole',
    '--name',$buildName,
    '--distpath', (Join-Path $here 'dist'),
    '--workpath', (Join-Path $here 'build'),
    '--specpath', (Join-Path $here 'build'),
    '--paths', $appDir,
    '--manifest', ([System.IO.Path]::GetFullPath((Join-Path $here 'IRtool.manifest'))),
    '--hidden-import','PyQt6.sip',
    '--hidden-import','PyQt6.QtCore',
    '--hidden-import','PyQt6.QtGui',
    '--hidden-import','PyQt6.QtWidgets',
    '--hidden-import','PyQt6.QtSvg',
    '--hidden-import','core.sysmon',
    '--hidden-import','core.sysmon.models',
    '--hidden-import','core.sysmon.parser',
    '--hidden-import','core.sysmon.subscriber',
    '--hidden-import','core.sysmon.config_manager',
    '--hidden-import','win32service',
    '--hidden-import','win32serviceutil',
    '--hidden-import','win32evtlog',
    '--hidden-import','win32api',
    '--hidden-import','win32con',
    '--hidden-import','win32security',
    '--hidden-import','winerror',
    '--collect-binaries','pywin32',
    '--collect-binaries','PyQt6',
    '--add-data', "$(Join-Path $appDir 'data\rules.json');data",
    '--add-data', "$(Join-Path $appDir 'tools\autorunsc64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\sigcheck64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\Sysmon64.exe');tools",
    '--add-data', "$(Join-Path $appDir 'tools\sysmon_config.xml');tools",
    '--add-data', "$(Join-Path $appDir 'ui\_check.svg');ui",
    '--add-data', "$(Join-Path $appDir 'ui\_close.svg');ui",
    '--add-data', "$(Join-Path $appDir 'ui\_expand.svg');ui",
    '--add-data', "$(Join-Path $appDir 'ui\_question.svg');ui",
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
    '--exclude-module','PyQt6.QtTest',
    '--exclude-module','PyQt6.QtTextToSpeech',
    '--exclude-module','PyQt6.QtWebChannel',
    '--exclude-module','PyQt6.QtWebEngineCore',
    '--exclude-module','PyQt6.QtWebEngineWidgets',
    '--exclude-module','PyQt6.QtWebSockets',
    '--exclude-module','PyQt6.QtXml',
    '--exclude-module','PyQt6.QtXmlPatterns'
)

$buildArgs += '--onedir'
$modeStr = 'onedir (directory)'
Write-Host "Mode: $modeStr" -ForegroundColor Green

$buildArgs += (Join-Path $appDir 'main.py')

Write-Host ""
Write-Host "Building..." -ForegroundColor Cyan
$env:PYINSTALLER_CLEANUP_CONFIRM = 'yes'
& $python @buildArgs --noconfirm

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Build Success!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green

    $dirPath = Join-Path $here "dist\$outputName"

    Set-Content -Path (Join-Path $dirPath ".version") -Value $appVersion -NoNewline

    if ($Mode -eq 'onedir-7z') {
        Write-Host ""
        Write-Host "Creating 7z self-extracting archive..." -ForegroundColor Cyan

        $logsDir = Join-Path $dirPath "logs"
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
        $configDir = Join-Path $dirPath "config"
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null

        $archivePath = Join-Path $here "dist\$outputName.7z"
        $sfxPath = Join-Path $here "dist\$outputName-7z.exe"

        if (Test-Path $sfxPath) { Remove-Item $sfxPath -Force -ErrorAction SilentlyContinue }
        if (Test-Path $archivePath) { Remove-Item $archivePath -Force -ErrorAction SilentlyContinue }

        $tempDir = Join-Path $here "dist\temp_7z"
        if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
        New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

        $versionDir = Join-Path $tempDir $outputName
        Copy-Item $dirPath $versionDir -Recurse -Force

        Push-Location $tempDir
        & $sevenZip a -t7z -m0=lzma2 -mx=9 "$archivePath" *
        Pop-Location

        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

        if ($LASTEXITCODE -eq 0) {
            $sevenZipDir = Split-Path $sevenZip -ErrorAction SilentlyContinue
            $sfxModule = $null
            if ($sevenZipDir) { $sfxModule = Join-Path $sevenZipDir '7z.sfx' }
            if (-not $sfxModule -or -not (Test-Path $sfxModule)) {
                $sfxModule = Get-Command 7z.sfx -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
            }
            if (-not $sfxModule -or -not (Test-Path $sfxModule)) {
                foreach ($p in @('C:\Program Files\7-Zip\7z.sfx', 'C:\Program Files (x86)\7-Zip\7z.sfx')) {
                    if (Test-Path $p) { $sfxModule = $p; break }
                }
            }
            if ($sfxModule -and (Test-Path $sfxModule)) {
                $configFile = Join-Path $here 'dist\sfx_config.txt'
                $templateFile = Join-Path $here 'sfx_config_template.txt'
                if (Test-Path $templateFile) {
                    $templateContent = Get-Content $templateFile -Raw
                    $configContent = $templateContent.Replace('{VERSION}', $appVersion).Replace('{OUTPUTNAME}', $outputName)
                    Set-Content -Path $configFile -Value $configContent -Encoding UTF8
                } else {
                    $sb = New-Object System.Text.StringBuilder
                    [void]$sb.AppendLine(';!@Install@!UTF-8!')
                    [void]$sb.AppendLine("Title=IRtool v$appVersion")
                    [void]$sb.AppendLine('BeginPrompt=Extract and run IRtool?')
                    [void]$sb.AppendLine("ExtractPath=%TEMP%\IRtool-$appVersion-%PID%")
                    [void]$sb.AppendLine('OverwriteMode=0')
                    [void]$sb.AppendLine("GUIRunOnce=%TEMP%\IRtool-$appVersion-%PID%\$outputName.exe")
                    [void]$sb.AppendLine(';!@InstallEnd@!')
                    Set-Content -Path $configFile -Value $sb.ToString() -Encoding UTF8
                }

                $sfxBytes = [System.IO.File]::ReadAllBytes($sfxModule)
                $configBytes = [System.IO.File]::ReadAllBytes($configFile)
                $archiveBytes = [System.IO.File]::ReadAllBytes($archivePath)

                $totalLen = $sfxBytes.Length + $configBytes.Length + $archiveBytes.Length
                $outputBytes = New-Object byte[] $totalLen
                [System.Array]::Copy($sfxBytes, 0, $outputBytes, 0, $sfxBytes.Length)
                [System.Array]::Copy($configBytes, 0, $outputBytes, $sfxBytes.Length, $configBytes.Length)
                [System.Array]::Copy($archiveBytes, 0, $outputBytes, $sfxBytes.Length + $configBytes.Length, $archiveBytes.Length)

                [System.IO.File]::WriteAllBytes($sfxPath, $outputBytes)

                Remove-Item $archivePath -ErrorAction SilentlyContinue
                Remove-Item $configFile -ErrorAction SilentlyContinue

                $sfxSize = (Get-Item $sfxPath).Length / 1MB
                $sfxSizeMB = [math]::Round($sfxSize, 2)
                Write-Host ""
                Write-Host "========================================" -ForegroundColor Green
                Write-Host "Self-extracting archive created!" -ForegroundColor Green
                Write-Host "========================================" -ForegroundColor Green
                Write-Host "Output: $sfxPath" -ForegroundColor Yellow
                Write-Host "Size: $sfxSizeMB MB" -ForegroundColor Yellow
                Write-Host "Type: Self-extracting archive (extracts and runs automatically)" -ForegroundColor Cyan
                Write-Host ""
                Write-Host "Usage: Double-click $outputName.exe to extract and run" -ForegroundColor White

                $zipPath = Join-Path $here "dist\$outputName.zip"
                if (Test-Path $zipPath) { Remove-Item $zipPath -Force -ErrorAction SilentlyContinue }
                Write-Host ""
                Write-Host "Wrapping in ZIP archive ..." -ForegroundColor Cyan
                & $sevenZip a -tzip -mx=5 "$zipPath" "$sfxPath"
                if ($LASTEXITCODE -eq 0) {
                    $zipSize = (Get-Item $zipPath).Length / 1MB
                    $zipSizeMB = [math]::Round($zipSize, 2)
                    $zipMsg = "ZIP created: $zipPath ($zipSizeMB MB)"
                    Write-Host $zipMsg -ForegroundColor Green
                } else {
                    Write-Host "ZIP creation failed, SFX is still available" -ForegroundColor Yellow
                }
            } else {
                Write-Host "7z.sfx module not found, keeping .7z archive" -ForegroundColor Yellow
                $archiveSize = (Get-Item $archivePath).Length / 1MB
                $archiveSizeMB = [math]::Round($archiveSize, 2)
                Write-Host "Archive: $archivePath" -ForegroundColor Yellow
                Write-Host "Size: $archiveSizeMB MB" -ForegroundColor Yellow
            }
        }
    } else {
        if (Test-Path $dirPath) {
            $logsDir = Join-Path $dirPath "logs"
            New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
            $configDir = Join-Path $dirPath "config"
            New-Item -ItemType Directory -Force -Path $configDir | Out-Null

            $size = (Get-ChildItem $dirPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
            $sizeMB = [math]::Round($size, 2)
            Write-Host ""
            Write-Host "Output: $dirPath\" -ForegroundColor Yellow
            Write-Host "Total Size: $sizeMB MB" -ForegroundColor Yellow
            Write-Host "Type: Directory (fast startup, stable)" -ForegroundColor Green
        }
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

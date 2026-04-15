# IRtool Release Build Script
# Build Type: onedir + 7z SFX (self-extracting)
# Version: 1.1.1

param(
    [ValidateSet('onedir','onedir-7z')] [string]$Mode = 'onedir-7z'
)

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
Write-Host "  IRtool Release Build" -ForegroundColor Cyan
Write-Host "  Version: $appVersion ($buildType)" -ForegroundColor Cyan
Write-Host "  Date: $buildDate" -ForegroundColor Cyan
Write-Host "  Mode: $Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check 7z for onedir-7z mode
$sevenZip = $null
if ($Mode -eq 'onedir-7z') {
    if (Get-Command 7z -ErrorAction SilentlyContinue) {
        $sevenZip = '7z'
    } elseif (Test-Path 'C:\Program Files\7-Zip\7z.exe') {
        $sevenZip = 'C:\Program Files\7-Zip\7z.exe'
    } elseif (Test-Path 'C:\Program Files (x86)\7-Zip\7z.exe') {
        $sevenZip = 'C:\Program Files (x86)\7-Zip\7z.exe'
    }

    if (-not $sevenZip) {
        Write-Host "7-Zip not found. Please install 7-Zip or use onedir mode." -ForegroundColor Red
        Write-Host "Download: https://www.7-zip.org/" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "7-Zip found: $sevenZip" -ForegroundColor Green
}

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

    if ($Mode -eq 'onedir-7z') {
        Write-Host ""
        Write-Host "Creating 7z self-extracting archive..." -ForegroundColor Cyan

        # Create logs and config directories inside the build
        $logsDir = Join-Path $dirPath "logs"
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
        $configDir = Join-Path $dirPath "config"
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null

        # Paths for 7z creation
        $archivePath = Join-Path $here "dist\$outputName.7z"
        $sfxPath = Join-Path $here "dist\$outputName-7z.exe"    # 打包文件添加 -7z 后缀，避免与解压后的主程序同名

        # Clean up old files
        if (Test-Path $sfxPath) {
            Remove-Item $sfxPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path $archivePath) {
            Remove-Item $archivePath -Force -ErrorAction SilentlyContinue
        }

        # Create 7z archive with version folder structure
        # First create a temp directory with the correct structure
        $tempDir = Join-Path $here "dist\temp_7z"
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
        
        # Copy build output to temp dir with version folder name
        $versionDir = Join-Path $tempDir $outputName
        Copy-Item $dirPath $versionDir -Recurse -Force
        
        # Create 7z archive from temp dir
        Push-Location $tempDir
        & $sevenZip a -t7z -m0=lzma2 -mx=9 "$archivePath" *
        Pop-Location
        
        # Clean up temp dir
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

        if ($LASTEXITCODE -eq 0) {
            # Get 7z SFX module
            $sfxModule = Join-Path (Split-Path $sevenZip) '7z.sfx'
            if (Test-Path $sfxModule) {
                # Create config file for SFX from template
                $configFile = Join-Path $here 'dist\sfx_config.txt'
                $templateFile = Join-Path $here 'sfx_config_template.txt'
                if (Test-Path $templateFile) {
                    $templateContent = Get-Content $templateFile -Raw
                    $configContent = $templateContent.Replace('{VERSION}', $appVersion).Replace('{OUTPUTNAME}', $outputName)
                    Set-Content -Path $configFile -Value $configContent -Encoding UTF8
                } else {
                    # Fallback: create minimal config
                    $configContent = ";!@Install@!UTF-8!`nTitle=`"IRtool v$appVersion`"`nBeginPrompt=`"Extract and run IRtool?`"`nExtractPath=`"%TEMP%\IRtool-$appVersion-%PID%`"`nOverwriteMode=0`nGUIRunOnce=`"%TEMP%\IRtool-$appVersion-%PID%\$outputName.exe`"`n;!@InstallEnd@!`n"
                    Set-Content -Path $configFile -Value $configContent -Encoding UTF8
                }

                # Combine SFX module + config + archive
                $sfxBytes = [System.IO.File]::ReadAllBytes($sfxModule)
                $configBytes = [System.IO.File]::ReadAllBytes($configFile)
                $archiveBytes = [System.IO.File]::ReadAllBytes($archivePath)

                $outputBytes = New-Object byte[] ($sfxBytes.Length + $configBytes.Length + $archiveBytes.Length)
                [System.Array]::Copy($sfxBytes, 0, $outputBytes, 0, $sfxBytes.Length)
                [System.Array]::Copy($configBytes, 0, $outputBytes, $sfxBytes.Length, $configBytes.Length)
                [System.Array]::Copy($archiveBytes, 0, $outputBytes, $sfxBytes.Length + $configBytes.Length, $archiveBytes.Length)

                [System.IO.File]::WriteAllBytes($sfxPath, $outputBytes)

                # Clean up
                Remove-Item $archivePath -ErrorAction SilentlyContinue
                Remove-Item $configFile -ErrorAction SilentlyContinue

                $sfxSize = (Get-Item $sfxPath).Length / 1MB
                Write-Host ""
                Write-Host "========================================" -ForegroundColor Green
                Write-Host "Self-extracting archive created!" -ForegroundColor Green
                Write-Host "========================================" -ForegroundColor Green
                Write-Host "Output: $sfxPath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($sfxSize,2)) MB" -ForegroundColor Yellow
                Write-Host "Type: Self-extracting archive (extracts and runs automatically)" -ForegroundColor Cyan
                Write-Host ""
                Write-Host "Usage: Double-click $outputName.exe to extract and run" -ForegroundColor White
            } else {
                Write-Host "7z.sfx module not found, keeping .7z archive" -ForegroundColor Yellow
                $archiveSize = (Get-Item $archivePath).Length / 1MB
                Write-Host "Archive: $archivePath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($archiveSize,2)) MB" -ForegroundColor Yellow
            }
        }
    } else {
        # onedir mode - just show info
        if (Test-Path $dirPath) {
            # Create logs directory
            $logsDir = Join-Path $dirPath "logs"
            New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

            # Create config directory
            $configDir = Join-Path $dirPath "config"
            New-Item -ItemType Directory -Force -Path $configDir | Out-Null

            $size = (Get-ChildItem $dirPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
            Write-Host ""
            Write-Host "Output: $dirPath\" -ForegroundColor Yellow
            Write-Host "Total Size: $([math]::Round($size,2)) MB" -ForegroundColor Yellow
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

param(
    [ValidateSet('onefile','onedir','onedir-upx','onedir-7z')] [string]$Mode = 'onedir-7z'
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

# Check 7z
$sevenZip = $null
if (Get-Command 7z -ErrorAction SilentlyContinue) {
    $sevenZip = '7z'
} elseif (Test-Path 'C:\Program Files\7-Zip\7z.exe') {
    $sevenZip = 'C:\Program Files\7-Zip\7z.exe'
} elseif (Test-Path 'C:\Program Files (x86)\7-Zip\7z.exe') {
    $sevenZip = 'C:\Program Files (x86)\7-Zip\7z.exe'
}

if ($Mode -eq 'onedir-7z' -and -not $sevenZip) {
    Write-Host "7-Zip not found. Please install 7-Zip or use other modes." -ForegroundColor Red
    Write-Host "Download: https://www.7-zip.org/" -ForegroundColor Yellow
    exit 1
}

# Set output name based on mode
switch ($Mode) {
    'onefile' { $outputName = 'sectool-onefile' }
    'onedir' { $outputName = 'sectool-onedir' }
    'onedir-upx' { $outputName = 'sectool-onedir-upx' }
    'onedir-7z' { $outputName = 'sectool-onedir-7z' }
}

Write-Host "Output name: $outputName" -ForegroundColor Cyan

# Base build args
$buildArgs = @(
    '-m','PyInstaller',
    '--clean',
    '--noconsole',
    '--name',$outputName,
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

# Mode selection
switch ($Mode) {
    'onefile' {
        $buildArgs += '--onefile'
        Write-Host "Mode: onefile (single file)" -ForegroundColor Cyan
    }
    'onedir' {
        $buildArgs += '--onedir'
        Write-Host "Mode: onedir (directory)" -ForegroundColor Cyan
    }
    'onedir-upx' {
        $buildArgs += '--onedir'
        if ($useUpx) {
            $buildArgs += @('--upx-dir', $upxDir)
            Write-Host "Mode: onedir + UPX compression" -ForegroundColor Green
        } else {
            Write-Host "Mode: onedir (UPX not found)" -ForegroundColor Yellow
        }
    }
    'onedir-7z' {
        $buildArgs += '--onedir'
        Write-Host "Mode: onedir + 7z self-extracting (Recommended)" -ForegroundColor Green
    }
}

# Entry
$buildArgs += 'app\main.py'

Write-Host "`nBuilding..." -ForegroundColor Cyan
& $python @buildArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "Build Success!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    # Create 7z self-extracting archive for onedir-7z mode
    if ($Mode -eq 'onedir-7z') {
        Write-Host "`nCreating 7z self-extracting archive..." -ForegroundColor Cyan
        
        $sourceDir = Join-Path $here "dist\$outputName"
        $archivePath = Join-Path $here "dist\$outputName.7z"
        $sfxPath = Join-Path $here "dist\$outputName.exe"
        
        # Create 7z archive
        & $sevenZip a -t7z -m0=lzma2 -mx=9 "$archivePath" "$sourceDir\*"
        
        if ($LASTEXITCODE -eq 0) {
            # Get 7z SFX module
            $sfxModule = Join-Path (Split-Path $sevenZip) '7z.sfx'
            if (Test-Path $sfxModule) {
                # Create config file for SFX
                $configFile = Join-Path $here 'dist\sfx_config.txt'
                @"
;!@Install@!UTF-8!
Title="SecTool - Security Analysis Tool"
BeginPrompt="This will extract SecTool to a temporary folder and run it. Continue?"
RunProgram="$outputName\$outputName.exe"
;!@InstallEnd@!
"@ | Out-File -FilePath $configFile -Encoding UTF8
                
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
                Write-Host "Self-extracting archive created!" -ForegroundColor Green
                Write-Host "Output: $sfxPath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($sfxSize,2)) MB" -ForegroundColor Yellow
            } else {
                Write-Host "7z.sfx module not found, keeping .7z archive" -ForegroundColor Yellow
                $archiveSize = (Get-Item $archivePath).Length / 1MB
                Write-Host "Archive: $archivePath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($archiveSize,2)) MB" -ForegroundColor Yellow
            }
        }
    }
    
    # Show output info
    switch ($Mode) {
        'onefile' {
            $exePath = Join-Path $here "dist\$outputName.exe"
            if (Test-Path $exePath) {
                $size = (Get-Item $exePath).Length / 1MB
                Write-Host "`nOutput: $exePath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($size,2)) MB" -ForegroundColor Yellow
                Write-Host "Type: Single executable file" -ForegroundColor Cyan
            }
        }
        'onedir' {
            $dirPath = Join-Path $here "dist\$outputName"
            if (Test-Path $dirPath) {
                $size = (Get-ChildItem $dirPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
                Write-Host "`nOutput: $dirPath\" -ForegroundColor Yellow
                Write-Host "Total Size: $([math]::Round($size,2)) MB" -ForegroundColor Yellow
                Write-Host "Type: Directory (fast startup)" -ForegroundColor Cyan
            }
        }
        'onedir-upx' {
            $dirPath = Join-Path $here "dist\$outputName"
            if (Test-Path $dirPath) {
                $size = (Get-ChildItem $dirPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
                Write-Host "`nOutput: $dirPath\" -ForegroundColor Yellow
                Write-Host "Total Size: $([math]::Round($size,2)) MB" -ForegroundColor Yellow
                Write-Host "Type: Directory with UPX compression" -ForegroundColor Cyan
            }
        }
        'onedir-7z' {
            $sfxPath = Join-Path $here "dist\$outputName.exe"
            if (Test-Path $sfxPath) {
                $size = (Get-Item $sfxPath).Length / 1MB
                Write-Host "`nOutput: $sfxPath" -ForegroundColor Yellow
                Write-Host "Size: $([math]::Round($size,2)) MB" -ForegroundColor Yellow
                Write-Host "Type: Self-extracting archive (extracts and runs automatically)" -ForegroundColor Cyan
            }
        }
    }
    
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "`nBuild Failed!" -ForegroundColor Red
}

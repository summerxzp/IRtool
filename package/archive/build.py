#!/usr/bin/env python3
"""Build script for IRtool using PyQt6 6.10.2"""

import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
app_dir = here.parent
output_name = "IRtool-v1.0.0"

print("=" * 50)
print("  IRtool Build (PyQt6 6.10.2)")
print("=" * 50)

# PyInstaller args
build_args = [
    sys.executable, "-m", "PyInstaller",
    "--clean",
    "--noconsole",
    "--name", output_name,
    "--distpath", str(here / "dist"),
    "--workpath", str(here / "build"),
    "--specpath", str(here / "build"),
    "--paths", str(app_dir),
    "--manifest", str(here / "IRtool.manifest"),
    "--hidden-import", "PyQt6.sip",
    "--hidden-import", "PyQt6.QtCore",
    "--hidden-import", "PyQt6.QtGui",
    "--hidden-import", "PyQt6.QtWidgets",
    "--collect-binaries", "PyQt6",
    "--add-data", f"{app_dir / 'data' / 'rules.json'};data",
    "--add-data", f"{app_dir / 'tools' / 'autorunsc64.exe'};tools",
    "--add-data", f"{app_dir / 'tools' / 'sigcheck64.exe'};tools",
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "scipy",
    "--exclude-module", "PIL",
    "--exclude-module", "Pillow",
    "--exclude-module", "unittest",
    "--exclude-module", "pydoc",
    "--exclude-module", "pdb",
    "--exclude-module", "doctest",
    "--exclude-module", "lib2to3",
    "--exclude-module", "tkinter",
    "--exclude-module", "email.mime",
    "--exclude-module", "http.server",
    "--exclude-module", "xmlrpc",
    "--exclude-module", "html",
    "--exclude-module", "_pytest",
    "--exclude-module", "pytest",
    "--exclude-module", "pytestqt",
    "--exclude-module", "PyQt6.Qt3DAnimation",
    "--exclude-module", "PyQt6.Qt3DCore",
    "--exclude-module", "PyQt6.Qt3DExtras",
    "--exclude-module", "PyQt6.Qt3DInput",
    "--exclude-module", "PyQt6.Qt3DLogic",
    "--exclude-module", "PyQt6.Qt3DRender",
    "--exclude-module", "PyQt6.QtBluetooth",
    "--exclude-module", "PyQt6.QtCharts",
    "--exclude-module", "PyQt6.QtConcurrent",
    "--exclude-module", "PyQt6.QtDataVisualization",
    "--exclude-module", "PyQt6.QtDesigner",
    "--exclude-module", "PyQt6.QtHelp",
    "--exclude-module", "PyQt6.QtLocation",
    "--exclude-module", "PyQt6.QtMultimedia",
    "--exclude-module", "PyQt6.QtMultimediaWidgets",
    "--exclude-module", "PyQt6.QtNetworkAuth",
    "--exclude-module", "PyQt6.QtNfc",
    "--exclude-module", "PyQt6.QtOpenGL",
    "--exclude-module", "PyQt6.QtOpenGLWidgets",
    "--exclude-module", "PyQt6.QtPdf",
    "--exclude-module", "PyQt6.QtPdfWidgets",
    "--exclude-module", "PyQt6.QtPositioning",
    "--exclude-module", "PyQt6.QtPrintSupport",
    "--exclude-module", "PyQt6.QtQml",
    "--exclude-module", "PyQt6.QtQuick",
    "--exclude-module", "PyQt6.QtQuick3D",
    "--exclude-module", "PyQt6.QtQuickWidgets",
    "--exclude-module", "PyQt6.QtRemoteObjects",
    "--exclude-module", "PyQt6.QtScxml",
    "--exclude-module", "PyQt6.QtSensors",
    "--exclude-module", "PyQt6.QtSerialPort",
    "--exclude-module", "PyQt6.QtSpatialAudio",
    "--exclude-module", "PyQt6.QtSql",
    "--exclude-module", "PyQt6.QtStateMachine",
    "--exclude-module", "PyQt6.QtSvg",
    "--exclude-module", "PyQt6.QtSvgWidgets",
    "--exclude-module", "PyQt6.QtTest",
    "--exclude-module", "PyQt6.QtTextToSpeech",
    "--exclude-module", "PyQt6.QtWebChannel",
    "--exclude-module", "PyQt6.QtWebEngineCore",
    "--exclude-module", "PyQt6.QtWebEngineWidgets",
    "--exclude-module", "PyQt6.QtWebSockets",
    "--exclude-module", "PyQt6.QtXml",
    "--exclude-module", "PyQt6.QtXmlPatterns",
    "--onedir",
    str(app_dir / "main.py")
]

print("Building...")
result = subprocess.run(build_args, cwd=str(app_dir))

if result.returncode == 0:
    print("\n" + "=" * 50)
    print("Build Success!")
    print("=" * 50)
    print(f"Output: {here / 'dist' / output_name}")
else:
    print("\nBuild Failed!")
    sys.exit(1)

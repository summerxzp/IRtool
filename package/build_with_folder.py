#!/usr/bin/env python3
"""Build script for IRtool - 打包到外层文件夹"""

import subprocess
import sys
import shutil
from pathlib import Path

here = Path(__file__).parent
app_dir = here.parent
output_name = "IRtool-v1.0.1"

print("=" * 50)
print("  IRtool Build v1.0.1 (PyQt6 6.10.2)")
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

if result.returncode != 0:
    print("\nBuild Failed!")
    sys.exit(1)

print("\n" + "=" * 50)
print("Build Success!")
print("=" * 50)

# 创建外层文件夹结构
dist_path = here / "dist"
source_dir = dist_path / output_name
temp_dir = dist_path / f"{output_name}-temp"
final_dir = temp_dir / output_name

# 清理临时目录
if temp_dir.exists():
    shutil.rmtree(temp_dir)

# 创建外层文件夹并移动内容
final_dir.mkdir(parents=True)
for item in source_dir.iterdir():
    shutil.move(str(item), str(final_dir / item.name))

# 创建 7z 压缩包（包含外层文件夹）
print("\nCreating 7z archive with outer folder...")
archive_path = dist_path / f"{output_name}.7z"
if archive_path.exists():
    archive_path.unlink()

subprocess.run([
    "C:/Program Files/7-Zip/7z.exe", "a", "-t7z", "-m0=lzma2", "-mx=9",
    str(archive_path), str(temp_dir / "*")
], cwd=str(dist_path))

# 创建自解压包
print("Creating self-extracting archive...")
sfx_module = Path("C:/Program Files/7-Zip/7z.sfx")
sfx_path = dist_path / f"{output_name}-7z.exe"

config_content = f""";!@Install@!UTF-8!
Title="IRtool v1.0.1"
ExtractPath="%TEMP%"
GUIRunOnce="%TEMP%\\{output_name}\\{output_name}.exe"
;!@InstallEnd@!
"""

with open(sfx_module, "rb") as f:
    sfx_bytes = f.read()
with open(archive_path, "rb") as f:
    archive_bytes = f.read()
config_bytes = config_content.encode("utf-8")

output_bytes = sfx_bytes + config_bytes + archive_bytes
with open(sfx_path, "wb") as f:
    f.write(output_bytes)

# 清理临时目录
shutil.rmtree(temp_dir)

print(f"\nCreated: {sfx_path}")
print(f"Size: {sfx_path.stat().st_size / 1024 / 1024:.2f} MB")
print("\n解压后会创建文件夹:", output_name)

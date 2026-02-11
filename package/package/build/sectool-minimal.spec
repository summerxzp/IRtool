# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = []
binaries += collect_dynamic_libs('PyQt6')


a = Analysis(
    ['..\\app\\main.py'],
    pathex=['D:\\project\\sectool_codex\\package\\package\\app'],
    binaries=binaries,
    datas=[('D:\\project\\sectool_codex\\package\\package\\app\\data\\rules.json', 'data'), ('D:\\project\\sectool_codex\\package\\package\\app\\tools\\autorunsc64.exe', 'tools'), ('D:\\project\\sectool_codex\\package\\package\\app\\tools\\sigcheck64.exe', 'tools')],
    hiddenimports=['PyQt6.sip', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'Pillow', 'unittest', 'pydoc', 'pdb', 'doctest', 'lib2to3', 'tkinter', 'email.mime', 'http.server', 'xmlrpc', 'html', '_pytest', 'pytest', 'pytestqt', 'PyQt6.Qt3DAnimation', 'PyQt6.Qt3DCore', 'PyQt6.Qt3DExtras', 'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic', 'PyQt6.Qt3DRender', 'PyQt6.QtBluetooth', 'PyQt6.QtCharts', 'PyQt6.QtConcurrent', 'PyQt6.QtDataVisualization', 'PyQt6.QtDesigner', 'PyQt6.QtHelp', 'PyQt6.QtLocation', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtNetworkAuth', 'PyQt6.QtNfc', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets', 'PyQt6.QtRemoteObjects', 'PyQt6.QtScxml', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtSpatialAudio', 'PyQt6.QtSql', 'PyQt6.QtStateMachine', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.QtTest', 'PyQt6.QtTextToSpeech', 'PyQt6.QtWebChannel', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebSockets', 'PyQt6.QtXml', 'PyQt6.QtXmlPatterns'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sectool-minimal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='sectool-minimal',
)

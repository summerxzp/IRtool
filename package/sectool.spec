# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app\\main.py'],
    pathex=['D:\\project\\sectool_codex\\package\\app'],
    binaries=[],
    datas=[('D:\\project\\sectool_codex\\package\\app\\data\\rules.json', 'data'), ('D:\\project\\sectool_codex\\package\\app\\tools\\autorunsc64.exe', 'tools'), ('D:\\project\\sectool_codex\\package\\app\\tools\\sigcheck64.exe', 'tools')],
    hiddenimports=['PyQt6.sip'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sectool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

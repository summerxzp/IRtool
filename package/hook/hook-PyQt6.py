from PyInstaller.utils.hooks import collect_all

# 不调用 QtLibraryInfo，直接收集全部 PyQt6 资源
datas, binaries, hiddenimports = collect_all("PyQt6")

# 明确补充 sip
hiddenimports += ["PyQt6.sip"]

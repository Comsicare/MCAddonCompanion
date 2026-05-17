from pathlib import Path

datas = [("frontend", "frontend")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["webview", "webview.platforms.winforms"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["venv", "customtkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MCAddonCompanion",
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MCAddonCompanion",
)

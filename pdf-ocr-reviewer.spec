from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH).resolve()

webui_datas, webui_binaries, webui_hiddenimports = collect_all("webui")
pymupdf_datas, pymupdf_binaries, pymupdf_hiddenimports = collect_all("pymupdf")

datas = [
    (str(ROOT / "ui"), "ui"),
    *webui_datas,
    *pymupdf_datas,
]

binaries = [
    *webui_binaries,
    *pymupdf_binaries,
]

hiddenimports = sorted(
    set(
        [
            "webui",
            "webui.webui",
            "pymupdf",
        ]
        + webui_hiddenimports
        + pymupdf_hiddenimports
    )
)

analysis = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="pdf-ocr-reviewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH).resolve()

webui_datas, webui_binaries, webui_hiddenimports = collect_all("webui")

if sys.platform.startswith("linux"):
    incompatible_linux_webui_arches = (
        "webui-linux-gcc-arm/",
        "webui-linux-gcc-arm64/",
    )
    webui_binaries = [
        entry
        for entry in webui_binaries
        if not any(
            marker in Path(entry[0]).as_posix()
            for marker in incompatible_linux_webui_arches
        )
    ]

datas = [
    (str(ROOT / "ui"), "ui"),
    *webui_datas,
]

binaries = [
    *webui_binaries,
]

hiddenimports = sorted(
    set(
        [
            "webui",
            "webui.webui",
            "pymupdf",
        ]
        + webui_hiddenimports
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
    strip=sys.platform.startswith("linux"),
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

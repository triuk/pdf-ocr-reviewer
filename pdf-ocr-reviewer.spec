import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from webui.load_library import _get_library_path


ROOT = Path(SPECPATH).resolve()

# The webui2 wheel may omit the Linux clang runtime selected by its loader.
# Fail here instead of shipping a binary that tries downloading it on first run.
if not Path(_get_library_path()).is_file():
    raise RuntimeError("WebUI native runtime missing: run python main.py --self-test in the build environment first.")
webui_datas, webui_binaries, webui_hiddenimports = collect_all("webui")

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

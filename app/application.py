from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .api import BackendApi


def get_ui_folder() -> Path:
    return Path(__file__).resolve().parent.parent / "ui"


@contextmanager
def external_program_environment() -> Iterator[None]:
    """Temporarily restore the system library path before WebUI launches a browser."""
    if not (sys.platform.startswith("linux") and getattr(sys, "frozen", False)):
        yield
        return

    library_path_key = "LD_LIBRARY_PATH"
    original_key = f"{library_path_key}_ORIG"
    runtime_value_present = library_path_key in os.environ
    runtime_value = os.environ.get(library_path_key)
    system_value = os.environ.get(original_key)

    if system_value is None:
        os.environ.pop(library_path_key, None)
    else:
        os.environ[library_path_key] = system_value

    try:
        yield
    finally:
        if runtime_value_present:
            os.environ[library_path_key] = runtime_value or ""
        else:
            os.environ.pop(library_path_key, None)


class PdfOcrReviewerApplication:
    def __init__(self, initial_folder: Path | None = None):
        self.initial_folder = initial_folder
        self.api = BackendApi(initial_folder=initial_folder)
        self.window: Any | None = None

    def run(self) -> None:
        try:
            from webui import webui
        except ImportError as exc:
            raise RuntimeError(
                "The 'webui2' package is not installed. Install requirements.txt first."
            ) from exc

        window_factory = getattr(webui, "Window", None) or getattr(webui, "window", None)
        if window_factory is None:
            raise RuntimeError("The installed WebUI package does not expose a window class.")

        self.window = window_factory()
        self.api.bind(self.window)
        self.window.set_root_folder(str(get_ui_folder()))

        with external_program_environment():
            shown = self.window.show("index.html")

        if shown is False:
            raise RuntimeError("WebUI could not open the application window.")
        try:
            webui.wait()
        finally:
            self.api.close()

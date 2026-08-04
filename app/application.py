from __future__ import annotations

from pathlib import Path
from typing import Any

from .api import BackendApi


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
        ui_folder = Path(__file__).resolve().parent.parent / "ui"
        self.window.set_root_folder(str(ui_folder))
        shown = self.window.show("index.html")
        if shown is False:
            raise RuntimeError("WebUI could not open the application window.")
        try:
            webui.wait()
        finally:
            self.api.close()

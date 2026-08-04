from __future__ import annotations

from pathlib import Path


class FolderDialogError(RuntimeError):
    """Raised when the native folder dialog cannot be opened."""


def select_folder(initial_folder: Path | None = None) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise FolderDialogError("Tkinter is not available in this Python installation.") from exc

    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    try:
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=str(initial_folder) if initial_folder else None,
            mustexist=True,
            title="Vyberte složku s PDF",
        )
    except tk.TclError as exc:
        raise FolderDialogError("The native folder dialog could not be opened.") from exc
    finally:
        root.destroy()

    return Path(selected).expanduser().resolve() if selected else None

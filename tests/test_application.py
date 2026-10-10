from __future__ import annotations

import os
from pathlib import Path

import pymupdf

from app import application


def test_frozen_startup_loads_pdfs_beside_executable(monkeypatch, tmp_path) -> None:
    binary_folder = tmp_path / 'installed'
    binary_folder.mkdir()
    bundle_folder = tmp_path / '_MEI123'
    bundle_folder.mkdir()
    launch_folder = tmp_path / 'launcher'
    launch_folder.mkdir()
    pdf_path = binary_folder / 'sample.pdf'
    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf_path)
    monkeypatch.setattr(application.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(application.sys, 'executable', str(binary_folder / 'pdf-ocr-reviewer'))
    monkeypatch.setattr(application.sys, '_MEIPASS', str(bundle_folder), raising=False)
    monkeypatch.chdir(launch_folder)
    monkeypatch.setenv('PDF_OCR_REVIEWER_STATE_DIR', str(tmp_path / 'state'))

    app = application.PdfOcrReviewerApplication()
    try:
        assert app.initial_folder == binary_folder
        assert app.api.current_folder == binary_folder
        assert list(app.api.files) == ['sample.pdf']
        assert app.api.startup_error is None
        assert not (binary_folder / 'pdf-ocr-reviewer.manifest.json').exists()
    finally:
        app.api.close()


def test_source_default_uses_project_folder(monkeypatch, tmp_path) -> None:
    monkeypatch.delattr(application.sys, 'frozen', raising=False)
    monkeypatch.chdir(tmp_path)
    assert application.get_default_folder() == Path(application.__file__).resolve().parent.parent


def test_main_folder_option_overrides_executable_folder(monkeypatch, tmp_path) -> None:
    import main

    chosen_folder = tmp_path / 'chosen'
    chosen_folder.mkdir()
    monkeypatch.setattr(application.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(application.sys, 'executable', str(tmp_path / 'pdf-ocr-reviewer'))
    monkeypatch.setattr(application.sys, 'argv', ['pdf-ocr-reviewer', '--folder', str(chosen_folder)])
    monkeypatch.setenv('PDF_OCR_REVIEWER_STATE_DIR', str(tmp_path / 'state'))
    observed = []

    def check_startup(app):
        try:
            observed.append(app.api.current_folder)
            assert app.initial_folder == chosen_folder
        finally:
            app.api.close()

    monkeypatch.setattr(application.PdfOcrReviewerApplication, 'run', check_startup)
    assert main.main() == 0
    assert observed == [chosen_folder]


def test_external_program_environment_restores_pyinstaller_library_path(monkeypatch) -> None:
    monkeypatch.setattr(application.sys, "platform", "linux")
    monkeypatch.setattr(application.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI123:/bundled")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/system/custom")

    with application.external_program_environment():
        assert os.environ["LD_LIBRARY_PATH"] == "/system/custom"

    assert os.environ["LD_LIBRARY_PATH"] == "/tmp/_MEI123:/bundled"
    assert os.environ["LD_LIBRARY_PATH_ORIG"] == "/system/custom"


def test_external_program_environment_removes_library_path_without_original(monkeypatch) -> None:
    monkeypatch.setattr(application.sys, "platform", "linux")
    monkeypatch.setattr(application.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI456")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)

    with application.external_program_environment():
        assert "LD_LIBRARY_PATH" not in os.environ

    assert os.environ["LD_LIBRARY_PATH"] == "/tmp/_MEI456"


def test_external_program_environment_is_noop_for_source_run(monkeypatch) -> None:
    monkeypatch.setattr(application.sys, "platform", "linux")
    monkeypatch.delattr(application.sys, "frozen", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/developer/value")

    with application.external_program_environment():
        assert os.environ["LD_LIBRARY_PATH"] == "/developer/value"

    assert os.environ["LD_LIBRARY_PATH"] == "/developer/value"

from __future__ import annotations

import os

from app import application


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

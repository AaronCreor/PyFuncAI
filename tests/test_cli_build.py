"""Offline coverage for the `build` command, including directory rejection."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyfuncai.cli import main


def test_build_rejects_empty_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """An empty directory target must fail before any code runs."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        main(["build", str(empty_dir)])
    assert "directory" in str(exc_info.value.code).lower()
    assert "not a script" in str(exc_info.value.code).lower()


def test_build_rejects_directory_with_main(tmp_path: Path):
    """A directory containing __main__.py must still be rejected without executing it."""
    target_dir = tmp_path / "pkg_dir"
    target_dir.mkdir()
    (target_dir / "__main__.py").write_text(
        "print('should never run')", encoding="utf-8"
    )
    with pytest.raises(SystemExit) as exc_info:
        main(["build", str(target_dir)])
    assert "directory" in str(exc_info.value.code).lower()


def test_build_missing_file(tmp_path: Path):
    """A missing file target must fail with the existing message."""
    missing = tmp_path / "does_not_exist.py"
    with pytest.raises(SystemExit) as exc_info:
        main(["build", str(missing)])
    assert "does not exist" in str(exc_info.value.code).lower()


def test_build_path_with_spaces(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """A valid script whose path contains spaces must still build."""
    spaced_dir = tmp_path / "my scripts"
    spaced_dir.mkdir()
    script = spaced_dir / "make_functions.py"
    script.write_text("# empty script\n", encoding="utf-8")
    assert main(["build", str(script)]) == 0
    captured = capsys.readouterr()
    assert "No PyFuncAI functions were created" in captured.out
    assert captured.err == ""

"""Offline subprocess coverage of CLI build target validation."""

import subprocess
import sys
from pathlib import Path

import pytest


def build(target: Path):
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from pyfuncai.cli import main; raise SystemExit(main())",
            "build",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("with_main", [False, True])
def test_build_rejects_directory_without_execution(tmp_path, with_main):
    target = tmp_path / "directory with spaces"
    target.mkdir()
    marker = tmp_path / "executed"
    if with_main:
        (target / "__main__.py").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
            encoding="utf-8",
        )
    result = build(target)
    assert result.returncode != 0
    assert "Target script is not a file:" in result.stderr
    assert str(target) in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
    assert not marker.exists()


def test_build_valid_script_with_spaces(tmp_path):
    script = tmp_path / "valid script.py"
    script.write_text("print('script executed')\n", encoding="utf-8")
    result = build(script)
    assert result.returncode == 0
    assert result.stderr == ""
    assert "script executed" in result.stdout
    assert "No PyFuncAI functions were created" in result.stdout


def test_build_missing_script_with_spaces(tmp_path):
    script = tmp_path / "missing script.py"
    result = build(script)
    assert result.returncode != 0
    assert "Target script does not exist:" in result.stderr
    assert str(script) in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""

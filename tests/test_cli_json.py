"""Offline coverage for machine-readable cache listings."""

import json
from pathlib import Path

import pytest

from pyfuncai.cache import DiskCache
from pyfuncai.cli import main


def test_cache_list_json_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    args = ["cache", "--cache-dir", str(tmp_path), "list"]
    assert main([*args, "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert captured.err == ""
    assert main(args) == 0
    assert capsys.readouterr().out == "Cache is empty.\n"


def test_cache_list_json_metadata_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    cache = DiskCache(tmp_path / "selected")
    entries = [
        cache.set(
            cache_key=key,
            function_name=name,
            signature="() -> str",
            source="def generated(): return 'private source'",
            provider={"provider": "fake", "model": "private model"},
            prompt="private prompt",
            mode=mode,
            allow_modules=[],
        )
        for key, name, mode in [
            ("z-first", "greet_é", "lazy"),
            ("a-second", "other", "eager"),
        ]
    ]
    args = ["cache", "--cache-dir", str(cache.cache_dir), "list"]
    assert main([*args, "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    expected = [
        {
            "cache_key": e.cache_key,
            "function_name": e.function_name,
            "mode": e.mode,
            "created_at": e.created_at,
        }
        for e in reversed(entries)
    ]
    assert json.loads(captured.out) == expected
    assert "private" not in captured.out
    assert main(args) == 0
    assert capsys.readouterr().out == "".join(
        f"{e.function_name}\t{e.mode}\t{e.created_at}\t{e.cache_key}\n"
        for e in reversed(entries)
    )


def test_cache_list_json_uses_default_directory(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert main(["cache", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []

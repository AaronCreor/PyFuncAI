"""Offline coverage for the `cache show` command."""

from pathlib import Path

import pytest

from pyfuncai.cache import DiskCache
from pyfuncai.cli import main


def _set_entry(cache: DiskCache, key: str = "valid-key") -> str:
    return cache.set(
        cache_key=key,
        function_name="greet",
        signature="(name: str) -> str",
        source="def greet(name): return f'Hello, {name}!'",
        provider={"provider": "fake", "model": "private model"},
        prompt="Say hello.",
        mode="eager",
        allow_modules=[],
    ).source


def test_cache_show_prints_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    cache = DiskCache(tmp_path / "selected")
    source = _set_entry(cache)
    args = ["cache", "--cache-dir", str(cache.cache_dir), "show"]
    assert main([*args, "valid-key"]) == 0
    captured = capsys.readouterr()
    assert captured.out == source + "\n"
    assert captured.err == ""


def test_cache_show_uses_cache_dir_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    cache = DiskCache(tmp_path / "selected")
    _set_entry(cache)
    args = ["cache", "--cache-dir", str(cache.cache_dir), "show"]
    assert main([*args, "valid-key"]) == 0
    assert capsys.readouterr().out != ""


def test_cache_show_missing_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    cache = DiskCache(tmp_path / "selected")
    args = ["cache", "--cache-dir", str(cache.cache_dir), "show"]
    assert main([*args, "does-not-exist"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "does-not-exist" in captured.err


def test_cache_show_invalid_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    cache = DiskCache(tmp_path / "selected")
    args = ["cache", "--cache-dir", str(cache.cache_dir), "show"]
    assert main([*args, "bad key!"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Invalid cache key" in captured.err


def test_cache_show_empty_cache(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    cache = DiskCache(tmp_path / "selected")
    args = ["cache", "--cache-dir", str(cache.cache_dir), "show"]
    assert main([*args, "any-key"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "any-key" in captured.err

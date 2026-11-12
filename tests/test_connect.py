"""Offline regression tests for publishing process-wide connection defaults."""

from pathlib import Path

import pytest

from pyfuncai import ConfigurationError, connect, create_function
from pyfuncai import core


@pytest.fixture(autouse=True)
def isolated_defaults(monkeypatch):
    monkeypatch.setattr(core, "_DEFAULT_PROVIDER", None)
    monkeypatch.setattr(core, "_DEFAULT_CACHE", None)


def lazy_function():
    return create_function("Return the input.", signature="(value: int) -> int")


def test_failed_reconnect_preserves_defaults(tmp_path: Path):
    original = connect("ollama", model="original", cache_dir=tmp_path / "original")
    existing = lazy_function()
    invalid_cache = tmp_path / "not-a-directory"
    invalid_cache.write_text("keep this file", encoding="utf-8")

    with pytest.raises(FileExistsError):
        connect("ollama", model="replacement", cache_dir=invalid_cache)

    later = lazy_function()
    assert later.provider is original
    assert later.cache_store is existing.cache_store
    assert existing.provider is original
    assert invalid_cache.read_text(encoding="utf-8") == "keep this file"


def test_failed_first_connect_leaves_defaults_unconfigured(tmp_path: Path):
    invalid_cache = tmp_path / "not-a-directory"
    invalid_cache.write_text("", encoding="utf-8")

    with pytest.raises(FileExistsError):
        connect("ollama", model="unused", cache_dir=invalid_cache)

    assert core._DEFAULT_PROVIDER is None
    assert core._DEFAULT_CACHE is None
    with pytest.raises(ConfigurationError, match="No provider configured"):
        lazy_function()


def test_successful_reconnect_only_changes_future_functions(tmp_path: Path):
    original = connect("ollama", model="original", cache_dir=tmp_path / "original")
    existing = lazy_function()
    replacement = connect("ollama", model="new", cache_dir=tmp_path / "new")
    later = lazy_function()

    assert later.provider is replacement
    assert later.cache_store.cache_dir == tmp_path / "new"
    assert existing.provider is original
    assert existing.cache_store.cache_dir == tmp_path / "original"
    assert later.cache_store is not existing.cache_store


def test_invalid_provider_preserves_defaults(tmp_path: Path):
    original = connect("ollama", model="original", cache_dir=tmp_path / "original")
    existing = lazy_function()
    with pytest.raises(ConfigurationError):
        connect("unknown-provider", model="unused", cache_dir=tmp_path / "unused")
    later = lazy_function()
    assert later.provider is original
    assert later.cache_store is existing.cache_store
    assert not (tmp_path / "unused").exists()

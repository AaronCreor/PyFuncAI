"""Regression coverage for signature, cache, and concurrent build failures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import gc
import inspect
import json
from pathlib import Path
import threading
from unittest.mock import patch
import weakref

import pytest

from pyfuncai import ConfigurationError, ValidationError, create_function
from pyfuncai.cache import DiskCache
from pyfuncai.core import _collect_functions, _registered_functions
from pyfuncai.signatures import signature_object
from test_pyfuncai import FakeProvider


def make(tmp_path: Path, provider=None, **kwargs):
    return create_function(
        "Return one.",
        signature="() -> int",
        function_name="f",
        provider=provider or FakeProvider("def f() -> int:\n    return 1"),
        cache_dir=str(tmp_path),
        **kwargs,
    )


@pytest.mark.parametrize(
    "signature",
    [
        "(x=__import__('builtins').print('executed')) -> int",
        "(x: print('executed')) -> int",
        "() -> int:\n    pass\nprint('executed')\n#",
        "(x, x) -> int",
        "(x=1, y) -> int",
        "(x=object()) -> int",
        "(x=set()) -> int",
        "not a signature",
    ],
)
def test_signature_rejects_execution(signature, capsys):
    with pytest.raises(ConfigurationError):
        signature_object(signature)
    assert capsys.readouterr().out == ""


def test_signature_metadata_supports_parameter_kinds_and_literals():
    signature = signature_object(
        "(x: int, /, y: str = 'ok', *values: float, flag: bool = True, **extra: int) -> list[str]"
    )
    assert signature.parameters["x"].kind == inspect.Parameter.POSITIONAL_ONLY
    assert signature.parameters["values"].kind == inspect.Parameter.VAR_POSITIONAL
    assert signature.parameters["extra"].kind == inspect.Parameter.VAR_KEYWORD
    assert signature.parameters["y"].default == "ok"
    assert signature.parameters["flag"].default is True
    assert signature.return_annotation == "list[str]"


@pytest.mark.parametrize(
    "option",
    [
        {"system_prompt": "different"},
        {"temperature": 0},
        {"max_output_tokens": 100},
    ],
)
def test_generation_settings_change_cache_key(tmp_path, option):
    assert make(tmp_path).cache_key != make(tmp_path, **option).cache_key


def test_template_version_changes_cache_key(tmp_path):
    function = make(tmp_path)
    original = function.cache_key
    with patch("pyfuncai.core.GENERATION_TEMPLATE_VERSION", 999):
        assert function.cache_key != original


def test_failed_generation_does_not_poison_cache(tmp_path):
    provider = FakeProvider("def f() -> int:\n    return +")
    function = make(tmp_path, provider)
    with pytest.raises(ValidationError):
        function.build()
    assert not list(tmp_path.glob("*.json"))
    provider.response_text = "def f() -> int:\n    return 1"
    assert function() == 1
    assert provider.calls == 2


def test_compilation_failure_does_not_persist(tmp_path):
    function = make(tmp_path)
    with patch(
        "pyfuncai.core.compile_function", side_effect=ValidationError("compile failure")
    ):
        with pytest.raises(ValidationError):
            function.build()
    assert not list(tmp_path.glob("*.json"))
    assert not function.is_built


def test_invalid_cached_source_is_evicted(tmp_path):
    function = make(tmp_path)
    assert function() == 1
    path = function.cache_store.path_for(function.cache_key)
    payload = json.loads(path.read_text())
    payload["source"] = "invalid python!"
    path.write_text(json.dumps(payload))
    other = make(tmp_path)
    with pytest.raises(ValidationError):
        other.build()
    assert not path.exists()
    assert other() == 1


def test_empty_allowlist_disables_imports(tmp_path):
    provider = FakeProvider("import math\ndef f() -> int:\n    return 1")
    function = make(tmp_path, provider, allow_modules=[])
    assert function.allow_modules == ()
    with pytest.raises(ValidationError):
        function.build()


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        "[]",
        "null",
        '{"schema_version": 999}',
        '{"schema_version": 1}',
        '{"schema_version": 1, "source": 42}',
    ],
)
def test_corrupt_cache_is_a_miss(tmp_path, payload):
    cache = DiskCache(tmp_path)
    cache.path_for("bad").write_text(payload)
    assert cache.get("bad") is None
    assert cache.entries() == []


@pytest.mark.parametrize(
    "key", ["../outside", "..\\outside", "/absolute", "C:\\outside", "", "a/b"]
)
def test_cache_paths_cannot_escape(tmp_path, key):
    cache = DiskCache(tmp_path)
    with pytest.raises(ConfigurationError):
        cache.get(key)
    with pytest.raises(ConfigurationError):
        cache.delete(key)


def test_cache_does_not_follow_external_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    cache = DiskCache(tmp_path / "cache")
    try:
        (cache.cache_dir / "link.json").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires additional Windows privileges.")
    with pytest.raises(ConfigurationError):
        cache.get("link")
    assert cache.entries() == []
    cache.clear()
    assert outside.exists()


def test_atomic_write_preserves_previous_entry_on_failure(tmp_path):
    function = make(tmp_path)
    function.build()
    path = function.cache_store.path_for(function.cache_key)
    original = path.read_bytes()
    with patch("pyfuncai.cache.os.replace", side_effect=OSError("interrupted")):
        with pytest.raises(OSError):
            function.build(force=True)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_concurrent_first_calls_generate_once(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class BlockingProvider(FakeProvider):
        def generate_text(self, **kwargs):
            started.set()
            assert release.wait(5)
            return super().generate_text(**kwargs)

    provider = BlockingProvider("def f() -> int:\n    return 1")
    function = make(tmp_path, provider)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(function) for _ in range(4)]
        try:
            assert started.wait(5)
        finally:
            release.set()
        assert [future.result(timeout=5) for future in futures] == [1] * 4
    assert provider.calls == 1


def test_registry_releases_unused_functions_and_scopes_cli_collection(tmp_path):
    function = make(tmp_path)
    ref = weakref.ref(function)
    assert function in _registered_functions()
    del function
    gc.collect()
    assert ref() is None
    with _collect_functions() as collected:
        make(tmp_path)
        gc.collect()
        assert len(collected) == 1
    ref = weakref.ref(collected[0])
    collected.clear()
    gc.collect()
    assert ref() is None


def test_common_exceptions_and_literal_defaults_work(tmp_path):
    function = create_function(
        "Reject negative numbers.",
        signature="(value: int = 1) -> int",
        function_name="positive",
        cache_dir=str(tmp_path),
        provider=FakeProvider(
            "def positive(value: int = 1) -> int:\n"
            '    if value < 0:\n        raise ValueError("negative")\n'
            "    return value"
        ),
    )
    assert function() == 1
    with pytest.raises(ValueError, match="negative"):
        function(-1)


@pytest.mark.parametrize(
    "options",
    [
        {"temperature": float("nan")},
        {"temperature": -1},
        {"max_output_tokens": 0},
        {"allow_modules": [None]},
        {"system_prompt": 42},
        {"mode": "unknown"},
    ],
)
def test_invalid_generation_config_is_rejected(tmp_path, options):
    with pytest.raises(ConfigurationError):
        make(tmp_path, **options)

"""Disk-backed cache support for generated functions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from pyfuncai.exceptions import ConfigurationError

CACHE_SCHEMA_VERSION = 1


@dataclass(slots=True)
class CacheEntry:
    """Represents one generated function stored on disk."""

    cache_key: str
    function_name: str
    signature: str
    source: str
    provider: dict[str, Any]
    created_at: str
    prompt: str
    mode: str
    allow_modules: list[str]


def default_cache_dir() -> Path:
    """Return the default cache directory for the current operating system."""

    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "PyFuncAI" / "cache"

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "pyfuncai"

    return Path.home() / ".cache" / "pyfuncai"


def make_cache_key(payload: dict[str, Any]) -> str:
    """Create a deterministic cache key for a generation request."""

    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class DiskCache:
    """Persist generated function source to disk for reuse across runs."""

    def __init__(self, cache_dir: str | os.PathLike[str] | None = None) -> None:
        """Initialize the cache store and ensure its root directory exists."""

        self.cache_dir = (
            Path(cache_dir) if cache_dir is not None else default_cache_dir()
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, cache_key: str) -> Path:
        """Return the JSON file path for a cache key."""

        if not isinstance(cache_key, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", cache_key
        ):
            raise ConfigurationError(
                "Invalid cache key: use letters, digits, '_' or '-'."
            )
        path = self.cache_dir / f"{cache_key}.json"
        if path.resolve().parent != self.cache_dir.resolve():
            raise ConfigurationError(
                "Cache entries must stay inside the cache directory."
            )
        return path

    def get(self, cache_key: str) -> CacheEntry | None:
        """Load a cache entry if it exists and matches the current schema version."""

        return self._read_entry(self.path_for(cache_key), cache_key)

    def _read_entry(self, path: Path, cache_key: str) -> CacheEntry | None:
        """Treat truncated, incompatible, or malformed entries as cache misses."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            if payload.pop("schema_version", None) != CACHE_SCHEMA_VERSION:
                return None
            entry = CacheEntry(**payload)
            strings = (
                entry.cache_key,
                entry.function_name,
                entry.signature,
                entry.source,
                entry.created_at,
                entry.prompt,
                entry.mode,
            )
            if (
                entry.cache_key != cache_key
                or not all(isinstance(value, str) for value in strings)
                or not isinstance(entry.provider, dict)
                or not isinstance(entry.allow_modules, list)
                or not all(isinstance(value, str) for value in entry.allow_modules)
            ):
                return None
            return entry
        except (OSError, UnicodeError, ValueError, TypeError):
            return None

    def entries(self) -> list[CacheEntry]:
        """Return all cache entries currently stored on disk."""

        entries: list[CacheEntry] = []
        for path in sorted(self.cache_dir.glob("*.json")):
            try:
                entry = self.get(path.stem)
            except ConfigurationError:
                continue
            if entry is not None:
                entries.append(entry)

        entries.sort(key=lambda entry: entry.created_at, reverse=True)
        return entries

    def delete(self, cache_key: str) -> bool:
        """Delete a cache entry by key and report whether a file was removed."""

        path = self.path_for(cache_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def clear(self) -> int:
        """Delete every cache entry and return the number of removed files."""

        removed = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                removed += self.delete(path.stem)
            except ConfigurationError:
                continue
        return removed

    def set(
        self,
        *,
        cache_key: str,
        function_name: str,
        signature: str,
        source: str,
        provider: dict[str, Any],
        prompt: str,
        mode: str,
        allow_modules: list[str],
    ) -> CacheEntry:
        """Store generated function source and its generation metadata."""

        entry = CacheEntry(
            cache_key=cache_key,
            function_name=function_name,
            signature=signature,
            source=source,
            provider=provider,
            created_at=datetime.now(timezone.utc).isoformat(),
            prompt=prompt,
            mode=mode,
            allow_modules=allow_modules,
        )
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            **asdict(entry),
        }
        target = self.path_for(cache_key)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.cache_dir,
                prefix=".pyfuncai-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return entry

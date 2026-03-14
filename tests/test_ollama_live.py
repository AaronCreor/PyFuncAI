"""Optional live integration test for a local Ollama instance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pylazy import connect, create_function

pytestmark = pytest.mark.skipif(
    os.environ.get("PYLAZY_RUN_OLLAMA_TESTS") != "1",
    reason="Set PYLAZY_RUN_OLLAMA_TESTS=1 to run live Ollama integration tests.",
)


def test_ollama_live_generation(tmp_path: Path) -> None:
    """Generate a small function through Ollama and verify the result."""

    model = os.environ.get("PYLAZY_OLLAMA_MODEL", "qwen3.5:latest")
    base_url = os.environ.get("PYLAZY_OLLAMA_BASE_URL", "http://localhost:11434")
    timeout = float(os.environ.get("PYLAZY_OLLAMA_TIMEOUT", "180"))

    connect(
        "ollama",
        model=model,
        base_url=base_url,
        timeout=timeout,
        cache_dir=str(tmp_path),
    )
    greet = create_function(
        "Return a short greeting for the provided name.",
        signature="(name: str) -> str",
        function_name="greet",
        mode="eager",
        cache=False,
    )

    assert greet("Alice") == "Hello, Alice!"
    assert greet.source is not None

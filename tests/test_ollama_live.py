"""Optional live Qwen/Ollama integration checks with deterministic specifications."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pyfuncai import OllamaProvider, create_function

pytestmark = pytest.mark.skipif(
    os.environ.get("PYFUNCAI_RUN_OLLAMA_TESTS") != "1",
    reason="Set PYFUNCAI_RUN_OLLAMA_TESTS=1 to run live Ollama integration tests.",
)


@pytest.mark.parametrize(
    "name,prompt,signature,cases,modules",
    [
        (
            "greet",
            "Return exactly 'Hello, ' followed by name and an exclamation mark.",
            "(name: str) -> str",
            [(("Alice",), "Hello, Alice!"), (("Bob",), "Hello, Bob!")],
            [],
        ),
        (
            "add",
            "Return the sum of the two integers a and b.",
            "(a: int, b: int) -> int",
            [((2, 3), 5), ((-4, 4), 0), ((0, 0), 0)],
            [],
        ),
        (
            "parse_numbers",
            "Use json to parse text containing a JSON array of integers and return that list.",
            "(text: str) -> list[int]",
            [(("[1, 2, 3]",), [1, 2, 3]), (("[]",), [])],
            ["json"],
        ),
        (
            "positive",
            "Return value unchanged if nonnegative; raise ValueError if value is negative.",
            "(value: int = 1) -> int",
            [((), 1), ((0,), 0), ((10,), 10)],
            [],
        ),
    ],
)
def test_ollama_live_generation(
    tmp_path: Path, name, prompt, signature, cases, modules
) -> None:
    provider = OllamaProvider(
        model=os.environ.get("PYFUNCAI_OLLAMA_MODEL", "qwen3.5:latest"),
        base_url=os.environ.get("PYFUNCAI_OLLAMA_BASE_URL", "http://localhost:11434"),
        timeout=float(os.environ.get("PYFUNCAI_OLLAMA_TIMEOUT", "180")),
    )
    options = dict(
        signature=signature,
        function_name=name,
        provider=provider,
        cache_dir=str(tmp_path),
        allow_modules=modules,
        mode="eager",
        temperature=0,
    )
    function = create_function(prompt, **options)
    for arguments, expected in cases:
        assert function(*arguments) == expected
    if name == "positive":
        with pytest.raises(ValueError):
            function(-1)
    assert function.source is not None
    with patch.object(
        provider, "generate_text", side_effect=AssertionError("Cache miss")
    ):
        cached = create_function(prompt, **options)
        for arguments, expected in cases:
            assert cached(*arguments) == expected

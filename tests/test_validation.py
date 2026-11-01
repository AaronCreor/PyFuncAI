"""Reject unsupported source shapes and verify model response extraction."""

import pytest

from pyfuncai import GenerationError, ValidationError
from pyfuncai.prompts import extract_python_source
from pyfuncai.validation import DEFAULT_ALLOWED_MODULES, validate_function_source


@pytest.mark.parametrize(
    "source",
    [
        "@print\ndef f() -> int:\n    return 1",
        "def f() -> int:\n    @print\n    def helper():\n        pass\n    return 1",
        "async def f() -> int:\n    return 1",
        'def f() -> int:\n    return eval("1")',
        "def f() -> int:\n    return (1).__class__",
        "def f() -> int:\n    from .math import floor\n    return 1",
        'print("side effect")\ndef f() -> int:\n    return 1',
        'def f() -> str:\n    return "1"',
        "def f() -> int:\n    return 1\ndef g():\n    return 2",
    ],
)
def test_invalid_source_is_rejected(source):
    with pytest.raises(ValidationError):
        validate_function_source(
            source,
            function_name="f",
            signature="() -> int",
            allowed_modules=DEFAULT_ALLOWED_MODULES,
        )


@pytest.mark.parametrize(
    "text",
    [
        "def f():\n    return 1",
        "```python\ndef f():\n    return 1\n```",
        '{"code": "def f():\\n    return 1"}',
        "Here is the code:\ndef f():\n    return 1",
    ],
)
def test_source_extraction(text):
    assert extract_python_source(text) == "def f():\n    return 1"


def test_empty_output_is_rejected():
    with pytest.raises(GenerationError):
        extract_python_source("  ")

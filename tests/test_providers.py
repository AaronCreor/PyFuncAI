"""Provider protocol tests use mocked HTTP and never require remote API keys."""

from __future__ import annotations

from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from pyfuncai import ConfigurationError, ProviderError
from pyfuncai.providers import (
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    _post_json,
    create_provider,
)


def response(payload):
    return BytesIO(json.dumps(payload).encode())


def post(**kwargs):
    return _post_json(
        "https://example.invalid/generate",
        payload={},
        headers=None,
        timeout=1,
        retry_backoff=0,
        **kwargs,
    )


@pytest.mark.parametrize(
    "failure", [TimeoutError(), URLError("offline"), OSError("reset")]
)
def test_transport_errors_use_provider_exception(failure):
    with patch("pyfuncai.providers.urlopen", side_effect=failure):
        with pytest.raises(ProviderError, match="connection"):
            post()


@pytest.mark.parametrize("body", [b"not json", b"\xff", b"[]", b"null"])
def test_malformed_responses_use_provider_exception(body):
    with patch("pyfuncai.providers.urlopen", return_value=BytesIO(body)):
        with pytest.raises(ProviderError):
            post()


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_http_errors_retry_with_a_bound(code):
    failure = HTTPError(
        "https://example.invalid", code, "failure", {}, BytesIO(b"secret")
    )
    with patch(
        "pyfuncai.providers.urlopen", side_effect=[failure, response({"ok": True})]
    ) as request:
        assert post(max_retries=1) == {"ok": True}
    assert request.call_count == 2


def test_retry_exhaustion_and_permanent_errors():
    with patch("pyfuncai.providers.urlopen", side_effect=TimeoutError()) as request:
        with pytest.raises(ProviderError):
            post(max_retries=2)
    assert request.call_count == 3
    failure = HTTPError(
        "https://example.invalid", 401, "failure", {}, BytesIO(b"secret")
    )
    with patch("pyfuncai.providers.urlopen", side_effect=failure) as request:
        with pytest.raises(ProviderError, match="401") as caught:
            post(max_retries=2)
    assert request.call_count == 1
    assert "secret" not in str(caught.value)


def test_ollama_payload_and_response():
    provider = OllamaProvider(model="qwen", max_retries=2)
    with patch(
        "pyfuncai.providers._post_json", return_value={"response": "def f(): pass"}
    ) as request:
        assert (
            provider.generate_text(
                prompt="generate",
                system_prompt="system",
                temperature=0,
                max_output_tokens=200,
            )
            == "def f(): pass"
        )
    options = request.call_args.kwargs
    assert options["payload"]["stream"] is False
    assert options["payload"]["options"] == {"temperature": 0, "num_predict": 200}
    assert options["payload"]["system"] == "system"
    assert options["max_retries"] == 2


def test_openai_joins_text_and_ignores_reasoning():
    payload = {
        "status": "completed",
        "output": [
            {"type": "reasoning", "content": [{"text": "private reasoning"}]},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "def f():"},
                    {"type": "output_text", "text": "\n    return 1"},
                ],
            },
        ],
    }
    provider = OpenAIProvider(model="test", api_key="test-key")
    with patch("pyfuncai.providers._post_json", return_value=payload) as request:
        assert (
            provider.generate_text(
                prompt="generate",
                system_prompt="system",
                temperature=0,
                max_output_tokens=200,
            )
            == "def f():\n    return 1"
        )
    assert request.call_args.args[0].endswith("/responses")
    assert request.call_args.kwargs["payload"]["max_output_tokens"] == 200


def test_openai_direct_output_text():
    provider = OpenAIProvider(model="test", api_key="test-key")
    with patch(
        "pyfuncai.providers._post_json", return_value={"output_text": "def f(): pass"}
    ):
        assert provider.generate_text(prompt="generate") == "def f(): pass"


def test_gemini_joins_one_candidate_without_thoughts_or_key_in_url():
    payload = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"thought": True, "text": "private reasoning"},
                        {"text": "def f():"},
                        {"text": "\n    return 1"},
                    ]
                },
            },
            {"content": {"parts": [{"text": "different candidate"}]}},
        ]
    }
    provider = GeminiProvider(model="test", api_key="test-key")
    with patch("pyfuncai.providers._post_json", return_value=payload) as request:
        assert (
            provider.generate_text(
                prompt="generate",
                system_prompt="system",
                temperature=0,
                max_output_tokens=200,
            )
            == "def f():\n    return 1"
        )
    assert "test-key" not in request.call_args.args[0]
    options = request.call_args.kwargs
    assert options["headers"]["x-goog-api-key"] == "test-key"
    assert options["payload"]["generationConfig"]["maxOutputTokens"] == 200


@pytest.mark.parametrize(
    "provider,payload",
    [
        (OllamaProvider, {"response": "partial", "done_reason": "length"}),
        (OpenAIProvider, {"output_text": "partial", "status": "incomplete"}),
        (GeminiProvider, {"candidates": [{"finishReason": "MAX_TOKENS"}]}),
        (OllamaProvider, {"response": None}),
        (OpenAIProvider, {"output": [None, {"content": None}]}),
        (GeminiProvider, {"candidates": [None, {"content": None}]}),
        (GeminiProvider, {"candidates": [{"finishReason": []}]}),
        (OpenAIProvider, {"output": [{"type": []}]}),
    ],
)
def test_incomplete_and_malformed_provider_output(provider, payload):
    options = {} if provider is OllamaProvider else {"api_key": "test-key"}
    with patch("pyfuncai.providers._post_json", return_value=payload):
        with pytest.raises(ProviderError):
            provider(model="test", **options).generate_text(prompt="generate")


@pytest.mark.parametrize(
    "options",
    [
        {"model": ""},
        {"model": "test", "timeout": 0},
        {"model": "test", "timeout": float("inf")},
        {"model": "test", "max_retries": 6},
        {"model": "test", "max_retries": True},
        {"model": "test", "retry_backoff": -1},
    ],
)
def test_invalid_provider_settings(options):
    with pytest.raises(ConfigurationError):
        OllamaProvider(**options)


def test_provider_creation_and_environment_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    assert create_provider("openai", model="test").api_key == "openai-key"
    assert create_provider("gemini", model="test").api_key == "gemini-key"
    assert create_provider(" OLLAMA ", model="test").provider_name == "ollama"
    with pytest.raises(ConfigurationError):
        create_provider("ollama", unknown=True)
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    for provider in [OpenAIProvider, GeminiProvider]:
        with pytest.raises(ConfigurationError):
            provider(model="test")

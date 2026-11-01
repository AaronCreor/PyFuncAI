"""Provider abstraction for local and remote model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
import json
import math
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pyfuncai.exceptions import ConfigurationError, ProviderError


class BaseProvider(ABC):
    """Abstract base class for providers that can generate Python source text."""

    provider_name: str

    def __init__(
        self,
        *,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
    ) -> None:
        """Store the common model selection and request timeout settings."""

        if not isinstance(model, str) or not model.strip():
            raise ConfigurationError("model must be a nonempty string.")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ConfigurationError("timeout must be a positive finite number.")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or not 0 <= max_retries <= 5
        ):
            raise ConfigurationError("max_retries must be an integer between 0 and 5.")
        if (
            isinstance(retry_backoff, bool)
            or not isinstance(retry_backoff, (int, float))
            or not math.isfinite(retry_backoff)
            or retry_backoff < 0
        ):
            raise ConfigurationError("retry_backoff must be finite and nonnegative.")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    @abstractmethod
    def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate a text completion for a prompt."""

    @abstractmethod
    def cache_identity(self) -> dict[str, Any]:
        """Return provider settings that affect cache reuse."""


class OllamaProvider(BaseProvider):
    """Generate code using a locally or remotely hosted Ollama instance."""

    provider_name = "ollama"

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
    ) -> None:
        """Configure an Ollama endpoint and model name."""

        super().__init__(
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.base_url = base_url.rstrip("/")

    def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Call Ollama's `/api/generate` endpoint and return the response text."""

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        if options:
            payload["options"] = options

        response = _post_json(
            f"{self.base_url}/api/generate",
            payload=payload,
            headers=None,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
        )
        if response.get("done") is False or response.get("done_reason") == "length":
            raise ProviderError(
                "Ollama returned incomplete output; increase the token limit."
            )
        text = response.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("Ollama returned an empty `response` field.")
        return text

    def cache_identity(self) -> dict[str, Any]:
        """Return cache-sensitive Ollama settings."""

        return {
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
        }


class OpenAIProvider(BaseProvider):
    """Generate code using the OpenAI Responses API."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
    ) -> None:
        """Configure an OpenAI API client using an explicit or env-based key."""

        super().__init__(
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url.rstrip("/")
        if not self.api_key:
            raise ConfigurationError(
                "OpenAIProvider requires `api_key=` or OPENAI_API_KEY."
            )

    def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Call the OpenAI Responses API and normalize the text output."""

        content = []
        if system_prompt:
            content.append(
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                }
            )
        content.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "input": content,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens

        response = _post_json(
            f"{self.base_url}/responses",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
        )

        if response.get("status") in (
            "incomplete",
            "failed",
            "cancelled",
            "in_progress",
            "queued",
        ):
            raise ProviderError(
                "OpenAI did not complete generation; check the token limit and model settings."
            )

        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        chunks = []
        for item in _object_list(response.get("output")):
            if item.get("type") not in (None, "message"):
                continue
            for content_item in _object_list(item.get("content")):
                text = content_item.get("text")
                if content_item.get("type") in (None, "output_text") and isinstance(
                    text, str
                ):
                    chunks.append(text)
        if chunks and "".join(chunks).strip():
            return "".join(chunks)

        raise ProviderError("OpenAI did not return any text content.")

    def cache_identity(self) -> dict[str, Any]:
        """Return cache-sensitive OpenAI settings."""

        return {
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
        }


class GeminiProvider(BaseProvider):
    """Generate code using the Gemini REST API."""

    provider_name = "gemini"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 60.0,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
    ) -> None:
        """Configure a Gemini API client using an explicit or env-based key."""

        super().__init__(
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.base_url = base_url.rstrip("/")
        if not self.api_key:
            raise ConfigurationError(
                "GeminiProvider requires `api_key=` or GEMINI_API_KEY."
            )

    def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Call Gemini and combine text parts from one completed candidate."""

        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        generation_config: dict[str, Any] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        if generation_config:
            payload["generationConfig"] = generation_config

        response = _post_json(
            f"{self.base_url}/models/{self.model}:generateContent",
            payload=payload,
            headers={"x-goog-api-key": self.api_key},
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
        )
        for candidate in _object_list(response.get("candidates")):
            if candidate.get("finishReason") not in (None, "STOP"):
                raise ProviderError(
                    "Gemini did not complete generation; check safety filters and the token limit."
                )
            content = candidate.get("content", {})
            if not isinstance(content, dict):
                continue
            chunks = [
                part["text"]
                for part in _object_list(content.get("parts"))
                if isinstance(part.get("text"), str) and not part.get("thought")
            ]
            if chunks and "".join(chunks).strip():
                return "".join(chunks)

        raise ProviderError("Gemini did not return any text content.")

    def cache_identity(self) -> dict[str, Any]:
        """Return cache-sensitive Gemini settings."""

        return {
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
        }


def create_provider(provider: str, **config: Any) -> BaseProvider:
    """Instantiate a provider class from a user-facing provider name."""

    normalized = provider.strip().lower() if isinstance(provider, str) else ""
    providers = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
    }
    if normalized in providers:
        try:
            return providers[normalized](**config)
        except TypeError as error:
            raise ConfigurationError(
                f"Invalid {normalized} provider configuration: {error}"
            ) from error

    raise ConfigurationError(
        f"Unsupported provider '{provider}'. Expected one of: ollama, openai, gemini."
    )


def _object_list(value: Any) -> list[dict[str, Any]]:
    """Read provider arrays defensively without exposing raw response data."""

    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _post_json(
    url: str,
    *,
    payload: Mapping[str, Any],
    headers: Mapping[str, str] | None,
    timeout: float,
    params: Mapping[str, str] | None = None,
    max_retries: int = 0,
    retry_backoff: float = 0.5,
) -> dict[str, Any]:
    """Issue a JSON POST request and return the decoded response payload."""

    target_url = url
    if params:
        target_url = f"{url}?{urlencode(dict(params))}"

    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    request = Request(
        target_url,
        data=json.dumps(dict(payload)).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise ProviderError("Provider response was not a JSON object.")
            return data
        except HTTPError as error:
            retryable = error.code in {429, 500, 502, 503, 504}
            error.close()
            if not retryable or attempt == max_retries:
                raise ProviderError(
                    f"Provider request failed with HTTP {error.code}."
                ) from error
        except (URLError, OSError) as error:
            if attempt == max_retries:
                raise ProviderError(
                    "Provider connection failed or timed out."
                ) from error
        except (ValueError, UnicodeError) as error:
            raise ProviderError(
                "Provider returned invalid JSON or text encoding."
            ) from error
        time.sleep(min(retry_backoff * (2**attempt), 10.0))
    raise ProviderError("Provider request exhausted its retry limit.")

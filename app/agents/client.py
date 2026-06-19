"""Injectable LLM client layer.

`LLMClient` is the seam the agents talk to. Tests pass a fake implementation, so
no live Anthropic calls happen during the build / free test suite. The real
`AnthropicLLMClient` is constructed only from `ANTHROPIC_API_KEY` in the
environment at runtime — the key is never hardcoded, logged, or surfaced.

Model ids (PRD section 8): Sonnet 4.6 = claude-sonnet-4-6, Opus 4.8 = claude-opus-4-8.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class LLMResponse:
    """Minimal normalized response: the assistant text plus the request echo.

    `request` captures exactly what was sent (model, system blocks, thinking,
    messages) so unit tests can assert prompt assembly, model selection, and
    cache_control placement without a live call.
    """

    text: str
    request: Dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """The seam. One method: send a message and get text back."""

    def complete(
        self,
        *,
        model: str,
        system: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int,
        thinking: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        ...


class AnthropicLLMClient:
    """Real client wrapping the official `anthropic` SDK.

    Imports the SDK lazily so the package imports (and the free test suite runs)
    without `anthropic` installed or any key present.
    """

    def __init__(self, api_key: str) -> None:
        # ponytail: lazy import keeps `import app` free of the SDK dependency.
        import anthropic

        # The key comes from the caller (which reads it from the environment).
        # We do not store it on the instance beyond what the SDK holds, and we
        # never log it.
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(
        self,
        *,
        model: str,
        system: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int,
        thinking: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if thinking is not None:
            kwargs["thinking"] = thinking

        resp = self._client.messages.create(**kwargs)
        # Concatenate text blocks (skip thinking blocks).
        text = "".join(
            getattr(block, "text", "") for block in resp.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(text=text, request=kwargs)


def build_default_client() -> Optional[LLMClient]:
    """Build the real client from the environment, or return None if no key.

    Returning None (rather than raising) lets the web app boot without a key;
    the pipeline surfaces a clean, sanitized error when a live run is attempted.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return AnthropicLLMClient(api_key=api_key)

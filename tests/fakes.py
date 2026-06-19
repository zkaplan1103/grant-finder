"""Test doubles — a fully offline fake LLM client. No live calls, no cost."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from app.agents.client import LLMResponse


class FakeLLMClient:
    """Records every request and returns scripted text replies.

    `replies` may be a single string (used for every call) or a list consumed in
    order. Each entry may also be a callable taking the request kwargs and
    returning a string, for content-dependent responses (e.g. revise loops).
    """

    def __init__(
        self,
        replies: Union[str, List[Union[str, Callable[[Dict[str, Any]], str]]]],
    ) -> None:
        self._replies = replies
        self._index = 0
        self.calls: List[Dict[str, Any]] = []

    def complete(
        self,
        *,
        model: str,
        system: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int,
        thinking: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        request = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "thinking": thinking,
        }
        self.calls.append(request)

        if isinstance(self._replies, str):
            entry: Union[str, Callable[[Dict[str, Any]], str]] = self._replies
        else:
            entry = self._replies[min(self._index, len(self._replies) - 1)]
            self._index += 1

        text = entry(request) if callable(entry) else entry
        return LLMResponse(text=text, request=request)

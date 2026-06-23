"""Robust JSON extraction from model text output.

Agents are instructed to reply with a single JSON object. We tolerate the common
wrappers (fenced code blocks, leading prose) by extracting the first balanced
{...} span, then hand the dict to the Pydantic model for validation.
"""

from __future__ import annotations

import json
from typing import Any, Dict


class AgentOutputError(ValueError):
    """Raised when the model output cannot be parsed into the expected shape."""


def extract_json_object(text: str, stop_reason: str | None = None) -> Dict[str, Any]:
    # A truncated response (hit max_tokens) has an unbalanced object; say so plainly
    # instead of the misleading generic "Unbalanced JSON" at the end.
    if stop_reason == "max_tokens":
        raise AgentOutputError("Model output truncated at max_tokens; raise max_tokens.")
    s = text.strip()

    # Strip a fenced ```json ... ``` or ``` ... ``` wrapper if present.
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()

    # Fast path: the whole thing is the object.
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Fallback: find the first balanced top-level {...} span.
    start = s.find("{")
    if start == -1:
        raise AgentOutputError("No JSON object found in model output.")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start : i + 1]
                try:
                    obj = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise AgentOutputError(f"Malformed JSON object: {exc}") from exc
                if not isinstance(obj, dict):
                    raise AgentOutputError("Top-level JSON is not an object.")
                return obj
    raise AgentOutputError("Unbalanced JSON object in model output.")

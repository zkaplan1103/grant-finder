"""Product agents: Match (Sonnet), Drafter (Sonnet), Verify (Opus).

The agent call layer is injectable (`LLMClient`) so the whole test suite runs
against a fake client with zero live API calls and zero cost. The real Anthropic
client is built only from `ANTHROPIC_API_KEY` in the environment, at runtime.
"""

from app.agents.client import (
    AnthropicLLMClient,
    LLMClient,
    LLMResponse,
    build_default_client,
)
from app.agents.drafter import DrafterAgent
from app.agents.match import MatchAgent
from app.agents.verify import VerifyAgent

__all__ = [
    "LLMClient",
    "LLMResponse",
    "AnthropicLLMClient",
    "build_default_client",
    "MatchAgent",
    "DrafterAgent",
    "VerifyAgent",
]

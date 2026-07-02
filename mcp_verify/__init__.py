"""mcp-verify: domain-agnostic verification of a DRAFT against a SOURCE."""

from mcp_verify.core import VerifiedClaim, VerifyReport, verify
from mcp_verify.prompt import SYSTEM_PROMPT

__all__ = ["SYSTEM_PROMPT", "VerifiedClaim", "VerifyReport", "verify"]

"""LLM-judge matcher for the eval harness.

The token matcher (eval/scorer.py) matches on surface form, so it can miscount
when Verify catches a claim in different words, or when a vague flag shares
tokens by coincidence. This judge asks a model the actual question — "does this
flag refer to this specific claim?" — to score on meaning instead.

Used only via `python -m eval.run --judge`; the token matcher stays the default
so CI and tests are free and deterministic.
"""

from __future__ import annotations

import json

from app.agents.client import LLMClient
from app.agents.parsing import extract_json_object
from app.models import UnsupportedClaim
from eval.cases import Sentence
from eval.scorer import Matcher

MODEL = "claude-haiku-4-5"  # cheap: this is a yes/no judgment, not the hard reasoning
MAX_TOKENS = 512

_SYSTEM = (
    "You judge whether a verifier's flagged claim refers to a specific target "
    "sentence from a grant draft. The verifier flags unsupported claims; we are "
    "checking whether its flag is ABOUT the target sentence (same underlying fact "
    "or assertion), regardless of wording. Paraphrase counts as a match; a flag "
    "about a different fact does not. Reply with a single JSON object and nothing "
    'else: {"refers_to": true|false}'
)


def make_judge_matcher(client: LLMClient) -> Matcher:
    """Build a Matcher backed by an LLM. Cached per (flag, sentence) within the
    process so the same pair isn't re-judged across cases in one run."""
    cache: dict[tuple[str, str], bool] = {}

    def judge(flag: UnsupportedClaim, sentence: Sentence) -> bool:
        key = (flag.claim, sentence.text)
        if key in cache:
            return cache[key]
        messages = [
            {
                "role": "user",
                "content": (
                    f"TARGET SENTENCE:\n{sentence.text}\n\n"
                    f"VERIFIER'S FLAGGED CLAIM:\n{flag.claim}\n\n"
                    "Does the flagged claim refer to the target sentence? JSON only."
                ),
            }
        ]
        resp = client.complete(
            model=MODEL,
            system=[{"type": "text", "text": _SYSTEM}],
            messages=messages,
            max_tokens=MAX_TOKENS,
        )
        try:
            data = extract_json_object(resp.text, resp.stop_reason)
            result = bool(data.get("refers_to", False))
        except Exception:
            result = False  # an unreadable judge verdict is a non-match, not a crash
        cache[key] = result
        return result

    return judge


def demo() -> None:
    """Self-check with a fake client: a 'yes' verdict matches, 'no' doesn't."""

    class _Fake:
        def __init__(self, verdict: bool) -> None:
            self._v = verdict

        def complete(self, **_kw):
            from app.agents.client import LLMResponse

            return LLMResponse(text=json.dumps({"refers_to": self._v}))

    s = Sentence("The org has a fleet of 30 vans.", planted=True, tag="t")
    f_yes = UnsupportedClaim(claim="claims to operate thirty vehicles", reason="x")
    assert make_judge_matcher(_Fake(True))(f_yes, s) is True
    assert make_judge_matcher(_Fake(False))(f_yes, s) is False
    print("judge demo: ok")


if __name__ == "__main__":
    demo()

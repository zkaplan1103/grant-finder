"""Abuse + cost guards for the public demo.

One expensive endpoint (`/api/match`) fires real Opus/Sonnet calls, so an
unbounded public demo is a money risk. This module bounds it three ways:

  1. per-IP rate limit  — stops one scripter hammering the endpoint
  2. global rate limit   — caps total concurrency/burn across all visitors
  3. daily spend kill    — hard ceiling on searches/day; the true backstop. Even
                           if the rate limits are evaded, spend cannot exceed
                           ~(daily cap × per-search cost).

ponytail: in-memory counters behind a lock, not Redis. This is a single-instance
demo — distributed state would be over-engineering. Known ceiling: counters reset
on restart and don't share across replicas. If this ever scales past one
instance, move the counters to Redis (the GuardState interface stays the same).

All limits are env-tunable so the deploy can dial them without a code change.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Tunables (env-overridable). Conservative defaults for a portfolio demo.
PER_IP_PER_MIN = _int_env("GUARD_PER_IP_PER_MIN", 3)
GLOBAL_PER_MIN = _int_env("GUARD_GLOBAL_PER_MIN", 20)
DAILY_SEARCH_CAP = _int_env("GUARD_DAILY_SEARCH_CAP", 300)

_WINDOW = 60.0  # seconds for the per-minute windows
_DAY = 86_400.0


@dataclass
class _Decision:
    ok: bool
    reason: str = ""  # user-facing, no internals


@dataclass
class GuardState:
    """Thread-safe in-memory rate + spend tracker. One instance per process."""

    per_ip: Dict[str, Deque[float]] = field(default_factory=dict)
    global_hits: Deque[float] = field(default_factory=deque)
    day_count: int = 0
    day_start: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _sweep(self, dq: Deque[float], now: float, window: float) -> None:
        cutoff = now - window
        while dq and dq[0] < cutoff:
            dq.popleft()

    def check_and_consume(self, ip: str) -> _Decision:
        """Atomically test all limits and, if allowed, record the request.

        Checked cheapest-first; the daily cap is the money backstop and is
        checked before the per-minute windows so a hammering client still can't
        push spend past the daily ceiling.
        """
        now = time.monotonic()
        with self._lock:
            # Daily spend ceiling (rolls every 24h).
            if now - self.day_start >= _DAY:
                self.day_start = now
                self.day_count = 0
            if self.day_count >= DAILY_SEARCH_CAP:
                return _Decision(False, "The demo's daily search limit has been reached. Try again tomorrow.")

            # Global per-minute.
            self._sweep(self.global_hits, now, _WINDOW)
            if len(self.global_hits) >= GLOBAL_PER_MIN:
                return _Decision(False, "The demo is busy right now. Please try again in a minute.")

            # Per-IP per-minute.
            dq = self.per_ip.get(ip)
            if dq is None:
                dq = deque()
                self.per_ip[ip] = dq
            self._sweep(dq, now, _WINDOW)
            if len(dq) >= PER_IP_PER_MIN:
                return _Decision(False, "You're sending searches too quickly. Please wait a minute.")

            # Allowed — record against all three.
            dq.append(now)
            self.global_hits.append(now)
            self.day_count += 1
            return _Decision(True)


def client_ip(request) -> str:
    """Best-effort client IP. Behind Railway's proxy the real IP is in
    X-Forwarded-For (first hop); fall back to the socket peer.

    Note: X-Forwarded-For is client-spoofable in general, but Railway's edge
    sets it, so the first entry is the real client when running behind their
    proxy. For a demo cost-guard this is sufficient; it is not an authentication
    signal and isn't used as one.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    client = getattr(request, "client", None)
    return getattr(client, "host", "unknown") if client else "unknown"

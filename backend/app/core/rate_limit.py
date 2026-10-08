"""In-memory, per-network rate limits (docs/DECISIONS.md D39-D44).

Keys are the client IP address only (plus the email for login attempts). No cookies,
fingerprints, or other per-consumer identifiers are used, and nothing here is persisted:
buckets live in process memory and are dropped once refilled.

Limits are per backend process. Running several API processes would need a shared store.
"""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.core.networks import in_networks, normalize_ip, parse_networks

# Buckets are pruned once more than this many keys are held.
MAX_TRACKED_KEYS = 10_000


@dataclass
class TokenBucketLimiter:
    """Each key may make `capacity` requests at once; spent tokens come back at
    `refill_per_second`. Steady traffic above the refill rate is blocked."""

    capacity: float
    refill_per_second: float
    clock: Callable[[], float] = time.monotonic
    _buckets: dict[str, tuple[float, float]] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def hit(self, key: str) -> float | None:
        """Take one token. Returns None if allowed, else seconds until one is available."""
        now = self.clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
            if tokens >= 1:
                self._buckets[key] = (tokens - 1, now)
                if len(self._buckets) > MAX_TRACKED_KEYS:
                    self._prune(now)
                return None
            self._buckets[key] = (tokens, now)
            return (1 - tokens) / self.refill_per_second

    def _prune(self, now: float) -> None:
        """Forget keys whose bucket has fully refilled; they behave like new keys."""
        full = [
            key
            for key, (tokens, last) in self._buckets.items()
            if tokens + (now - last) * self.refill_per_second >= self.capacity
        ]
        for key in full:
            del self._buckets[key]


class RateLimiters:
    """All limiters for one app instance, built from settings."""

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic):
        self.enabled = settings.rate_limit_enabled
        self.exempt = parse_networks(settings.rate_limit_exempt_ips)
        self.trusted_proxies = parse_networks(settings.trusted_proxy_ips)
        self.limiters = {
            "lookup": TokenBucketLimiter(
                capacity=settings.rate_limit_lookup_burst,
                refill_per_second=settings.rate_limit_lookup_refill_per_second,
                clock=clock,
            ),
            "login": TokenBucketLimiter(
                capacity=settings.rate_limit_login_per_minute,
                refill_per_second=settings.rate_limit_login_per_minute / 60,
                clock=clock,
            ),
            "register": TokenBucketLimiter(
                capacity=settings.rate_limit_register_per_hour,
                refill_per_second=settings.rate_limit_register_per_hour / 3600,
                clock=clock,
            ),
        }

    def client_ip(self, request: Request) -> str:
        """The connecting IP, or, when the connection comes from a trusted proxy (the Next.js
        server), the right-most X-Forwarded-For entry that is not itself a trusted proxy."""
        peer = request.client.host if request.client else ""
        if in_networks(peer, self.trusted_proxies):
            forwarded = request.headers.get("x-forwarded-for", "")
            for candidate in reversed([part.strip() for part in forwarded.split(",")]):
                if candidate and not in_networks(candidate, self.trusted_proxies):
                    return normalize_ip(candidate)
        return normalize_ip(peer)

    def enforce(self, request: Request, name: str, extra_key: str = "") -> None:
        """Raise 429 with Retry-After if this network has used up the `name` limit."""
        if not self.enabled:
            return
        ip = self.client_ip(request)
        if in_networks(ip, self.exempt):
            return
        retry_after = self.limiters[name].hit(f"{ip}|{extra_key}")
        if retry_after is not None:
            seconds = max(1, math.ceil(retry_after))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many requests from your network. Try again in {seconds} seconds.",
                headers={"Retry-After": str(seconds)},
            )


def enforce_rate_limit(request: Request, name: str, extra_key: str = "") -> None:
    limiters: RateLimiters = request.app.state.rate_limiters
    limiters.enforce(request, name, extra_key)


def limit_lookups(request: Request) -> None:
    """Route dependency for public product lookups:
    @router.post("/lookups/batch", dependencies=[Depends(limit_lookups)])"""
    enforce_rate_limit(request, "lookup")

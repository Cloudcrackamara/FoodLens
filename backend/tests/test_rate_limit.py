"""Per-network rate limits: token bucket behaviour, Retry-After, exemptions, proxy handling."""

from collections.abc import Callable
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rate_limit import RateLimiters, TokenBucketLimiter, limit_lookups

probe = APIRouter(prefix="/test-only")


@probe.get("/lookup")
def fake_lookup(_: Annotated[None, Depends(limit_lookups)]) -> dict:
    return {"ok": True}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def lookup_client(
    make_client: Callable[..., TestClient],
    clock: FakeClock | None = None,
    client_ip: str = "203.0.113.10",
    **setting_overrides,
) -> TestClient:
    config = settings(**setting_overrides)
    client = make_client(probe, settings=config, client_ip=client_ip)
    if clock is not None:
        client.app.state.rate_limiters = RateLimiters(config, clock=clock)
    return client


# --- Token bucket ------------------------------------------------------------------------


def test_bucket_allows_full_burst_then_blocks() -> None:
    bucket = TokenBucketLimiter(capacity=20, refill_per_second=1, clock=FakeClock())

    assert all(bucket.hit("net") is None for _ in range(20))
    assert bucket.hit("net") == pytest.approx(1.0)


def test_bucket_refills_over_time() -> None:
    clock = FakeClock()
    bucket = TokenBucketLimiter(capacity=20, refill_per_second=1, clock=clock)
    for _ in range(20):
        bucket.hit("net")

    clock.advance(1)
    assert bucket.hit("net") is None
    assert bucket.hit("net") is not None

    clock.advance(30)  # refills to capacity, never beyond
    assert sum(bucket.hit("net") is None for _ in range(25)) == 20


def test_bucket_keys_are_independent() -> None:
    bucket = TokenBucketLimiter(capacity=1, refill_per_second=1, clock=FakeClock())

    assert bucket.hit("network-a") is None
    assert bucket.hit("network-a") is not None
    assert bucket.hit("network-b") is None


# --- Lookup limit through the API ----------------------------------------------------------


def test_lookup_burst_is_allowed(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(make_client, clock=FakeClock())

    statuses = [client.get("/test-only/lookup").status_code for _ in range(20)]

    assert statuses == [200] * 20


def test_lookup_over_burst_gets_429_with_retry_after(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(make_client, clock=FakeClock())
    for _ in range(20):
        client.get("/test-only/lookup")

    response = client.get("/test-only/lookup")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert "Too many requests from your network" in response.json()["detail"]


def test_sustained_lookup_traffic_is_blocked(make_client: Callable[..., TestClient]) -> None:
    clock = FakeClock()
    client = lookup_client(make_client, clock=clock)

    # 2 requests per second for 60 seconds: double the 1/second refill.
    statuses = []
    for _ in range(120):
        statuses.append(client.get("/test-only/lookup").status_code)
        clock.advance(0.5)

    allowed = statuses.count(200)
    assert statuses.count(429) > 0
    assert 75 <= allowed <= 81  # burst of 20 + about 60 refilled tokens


def test_lookup_traffic_at_refill_rate_is_never_blocked(
    make_client: Callable[..., TestClient],
) -> None:
    clock = FakeClock()
    client = lookup_client(make_client, clock=clock)

    statuses = []
    for _ in range(100):
        statuses.append(client.get("/test-only/lookup").status_code)
        clock.advance(1)

    assert set(statuses) == {200}


def test_lookup_limits_are_configurable(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(make_client, clock=FakeClock(), rate_limit_lookup_burst=3)

    statuses = [client.get("/test-only/lookup").status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]


def test_exempt_ip_is_never_blocked(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(
        make_client, client_ip="192.168.1.20", rate_limit_exempt_ips="192.168.1.20, 10.0.0.0/24"
    )

    statuses = [client.get("/test-only/lookup").status_code for _ in range(200)]

    assert set(statuses) == {200}


def test_exempt_cidr_range_is_never_blocked(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(make_client, client_ip="10.0.0.77", rate_limit_exempt_ips="10.0.0.0/24")

    assert {client.get("/test-only/lookup").status_code for _ in range(50)} == {200}


def test_non_exempt_ip_is_still_limited(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(
        make_client, client_ip="192.168.1.21", rate_limit_exempt_ips="192.168.1.20"
    )

    assert 429 in {client.get("/test-only/lookup").status_code for _ in range(25)}


def test_rate_limiting_can_be_disabled(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(make_client, rate_limit_enabled=False)

    assert {client.get("/test-only/lookup").status_code for _ in range(50)} == {200}


def test_invalid_exempt_ip_fails_at_startup() -> None:
    with pytest.raises(ValidationError):
        settings(rate_limit_exempt_ips="192.168.1.300")


def test_ipv4_mapped_address_matches_ipv4_exemption(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(
        make_client, client_ip="::ffff:192.168.1.20", rate_limit_exempt_ips="192.168.1.20"
    )

    assert {client.get("/test-only/lookup").status_code for _ in range(30)} == {200}


def test_ipv4_mapped_and_plain_forms_share_one_bucket(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(
        make_client, clock=FakeClock(), client_ip="127.0.0.1", rate_limit_lookup_burst=1
    )

    first = client.get("/test-only/lookup", headers={"X-Forwarded-For": "192.168.1.30"})
    mapped = client.get("/test-only/lookup", headers={"X-Forwarded-For": "::ffff:192.168.1.30"})

    assert (first.status_code, mapped.status_code) == (200, 429)


# --- Client IP from the Next.js proxy -------------------------------------------------------


def test_networks_behind_trusted_proxy_get_separate_buckets(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(
        make_client, clock=FakeClock(), client_ip="127.0.0.1", rate_limit_lookup_burst=1
    )

    first = client.get("/test-only/lookup", headers={"X-Forwarded-For": "198.51.100.1"})
    second = client.get("/test-only/lookup", headers={"X-Forwarded-For": "198.51.100.2"})
    repeat = client.get("/test-only/lookup", headers={"X-Forwarded-For": "198.51.100.1"})

    assert (first.status_code, second.status_code, repeat.status_code) == (200, 200, 429)


def test_forwarded_header_from_untrusted_client_is_ignored(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(
        make_client, clock=FakeClock(), client_ip="203.0.113.50", rate_limit_lookup_burst=1
    )

    first = client.get("/test-only/lookup", headers={"X-Forwarded-For": "198.51.100.1"})
    spoofed = client.get("/test-only/lookup", headers={"X-Forwarded-For": "198.51.100.2"})

    assert (first.status_code, spoofed.status_code) == (200, 429)


def test_rightmost_untrusted_forwarded_entry_is_used(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(
        make_client, clock=FakeClock(), client_ip="127.0.0.1", rate_limit_lookup_burst=1
    )

    first = client.get("/test-only/lookup", headers={"X-Forwarded-For": "1.1.1.1, 198.51.100.7"})
    # Different left-hand (client-written) value, same real network on the right.
    second = client.get("/test-only/lookup", headers={"X-Forwarded-For": "2.2.2.2, 198.51.100.7"})

    assert (first.status_code, second.status_code) == (200, 429)


# --- Login and registration -----------------------------------------------------------------


def test_login_attempts_are_limited_per_ip_and_email(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(make_client, clock=FakeClock())
    body = {"email": "owner@example.com", "password": "wrong-password-1"}

    statuses = [client.post("/api/auth/login", json=body).status_code for _ in range(6)]
    blocked = client.post("/api/auth/login", json=body)
    other_email = client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "x"}
    )

    assert statuses == [401] * 5 + [429]
    assert blocked.headers["Retry-After"] == "12"  # one attempt refills every 12 seconds
    assert other_email.status_code == 401


def test_login_limit_counts_email_case_insensitively(
    make_client: Callable[..., TestClient],
) -> None:
    client = lookup_client(make_client, clock=FakeClock())

    for email in [
        "a@example.com",
        "A@example.com",
        "A@EXAMPLE.COM",
        "a@Example.com",
        "a@example.COM",
    ]:
        client.post("/api/auth/login", json={"email": email, "password": "wrong-password-1"})

    blocked = client.post("/api/auth/login", json={"email": "A@example.com", "password": "x"})
    assert blocked.status_code == 429


def test_registration_is_limited_per_hour(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(make_client, clock=FakeClock(), rate_limit_register_per_hour=2)

    def register(n: int) -> int:
        return client.post(
            "/api/auth/register",
            json={
                "email": f"user{n}@example.com",
                "password": "correct-horse-battery",
                "display_name": "Demo",
            },
        ).status_code

    statuses = [register(n) for n in range(3)]
    blocked = client.post(
        "/api/auth/register",
        json={
            "email": "late@example.com",
            "password": "correct-horse-battery",
            "display_name": "D",
        },
    )

    assert statuses == [201, 201, 429]
    assert int(blocked.headers["Retry-After"]) > 60


def test_rate_limited_response_sets_no_cookie(make_client: Callable[..., TestClient]) -> None:
    client = lookup_client(make_client, clock=FakeClock(), rate_limit_lookup_burst=1)
    client.get("/test-only/lookup")

    response = client.get("/test-only/lookup")

    assert response.status_code == 429
    assert "set-cookie" not in response.headers

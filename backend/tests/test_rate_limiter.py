from __future__ import annotations

from starlette.requests import Request

from app.core.rate_limiter import _client_ip


def _make_request(headers: list[tuple[bytes, bytes]], client: tuple[str, int] = ("172.18.0.1", 12345)) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/agents/register",
        "headers": headers,
        "client": client,
        "scheme": "https",
        "server": ("api.seabay.ai", 443),
        "query_string": b"",
    }
    return Request(scope)


def test_client_ip_prefers_cf_connecting_ip():
    req = _make_request([(b"cf-connecting-ip", b"203.0.113.10")])
    assert _client_ip(req) == "203.0.113.10"


def test_client_ip_uses_first_forwarded_hop():
    req = _make_request([(b"x-forwarded-for", b"198.51.100.8, 172.18.0.1")])
    assert _client_ip(req) == "198.51.100.8"


def test_client_ip_falls_back_to_real_ip():
    req = _make_request([(b"x-real-ip", b"192.0.2.55")])
    assert _client_ip(req) == "192.0.2.55"


def test_client_ip_falls_back_to_request_client():
    req = _make_request([], client=("172.18.0.1", 12345))
    assert _client_ip(req) == "172.18.0.1"

"""Default CORS origin regex: LAN-reachable names and literals, nothing public."""

import re

import pytest

from app.main import _PRIVATE_ORIGIN_RE

_matches = re.compile(_PRIVATE_ORIGIN_RE).fullmatch


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
        "http://10.0.0.1",
        "http://192.168.10.200:3000",
        "http://172.16.0.1:8000",
        # Names, not IPs: a compose service, a bare LAN hostname, and hosts under
        # the private-use suffixes.
        "http://frontend:3000",
        "http://ddlc-server:3000",
        "https://nas:3000",
        "http://nas.local:3000",
        "http://ddlc.internal",
        "http://box.home.arpa:3000",
    ],
)
def test_allows_lan_origins(origin):
    assert _matches(origin)


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example.com",
        "https://example.com:3000",
        "http://sub.example.com",
        # A private literal/name must not be a prefix of a public host.
        "http://192.168.10.200.evil.com",
        "http://frontend.evil.com",
        "http://nas.local.evil.com",
        # Wrong scheme, or something that isn't a bare origin.
        "ftp://frontend:3000",
        "http://frontend:3000/path",
        "http://frontend:3000 http://evil.example.com",
    ],
)
def test_rejects_public_and_malformed_origins(origin):
    assert not _matches(origin)

"""Identify API callers by *name* rather than by raw IP.

The rate limiter keys on ``request.client.host``, which is awkward to configure
in a compose deployment: every container the API sees has an ephemeral bridge
IP, so "the frontend may do 120/min, anything else 20" has no stable value to
put in ``.env``. ``RATE_LIMIT_CLIENTS`` therefore takes **names** — docker
compose service names (resolved through the embedded DNS at request time, so
restarts and ``--scale`` are handled), ordinary hostnames, or plain IPs/CIDRs —
and this module maps an incoming peer address back to whichever entry matched.
The matched entry's name is then the limiter key, so one bucket covers a whole
service no matter how its container IP changes.

Lookups are cached for ``RESOLVE_TTL_SECONDS``: DNS is consulted at most once
per name per TTL, and a failure is cached as "no addresses" so an unresolvable
name can't turn every request into a blocking lookup (it simply falls back to
per-IP keying until the next refresh).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

RESOLVE_TTL_SECONDS = 30.0

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class ClientRule:
    """One ``RATE_LIMIT_CLIENTS`` entry.

    ``name`` is both the configured token and the rate-limit key. ``network`` is
    set when the entry parsed as an IP/CIDR; otherwise the entry is a hostname
    (or compose service name) that is resolved at match time.
    """

    name: str
    max_per_min: int | None = None
    network: IPNetwork | None = None


def parse_client_rules(spec: str | None) -> list[ClientRule]:
    """Parse ``name[=per_minute]`` entries, comma separated.

    ``=`` separates the optional limit (not ``:``) so IPv6 literals stay
    unambiguous. Malformed entries are logged and skipped rather than taking the
    API down at import time over a typo in ``.env``.
    """
    rules: list[ClientRule] = []
    for raw in (spec or "").split(","):
        entry = raw.strip()
        if not entry:
            continue
        name, _, limit_text = entry.partition("=")
        name, limit_text = name.strip(), limit_text.strip()
        if not name:
            logger.warning("ignoring RATE_LIMIT_CLIENTS entry %r: empty name", entry)
            continue
        limit: int | None = None
        if limit_text:
            try:
                limit = int(limit_text)
            except ValueError:
                logger.warning("ignoring RATE_LIMIT_CLIENTS entry %r: limit is not a number", entry)
                continue
            if limit <= 0:
                logger.warning(
                    "ignoring RATE_LIMIT_CLIENTS entry %r: limit must be positive", entry
                )
                continue
        try:
            network: IPNetwork | None = ipaddress.ip_network(name, strict=False)
        except ValueError:
            network = None  # a hostname / compose service name, resolved later
        rules.append(ClientRule(name=name, max_per_min=limit, network=network))
    return rules


def resolve_hostname(name: str) -> frozenset[str]:
    """Best-effort A/AAAA lookup. Never raises: an unresolvable name (service not
    running yet, DNS blip) matches nothing until the cache entry expires."""
    try:
        infos = socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        logger.warning("cannot resolve rate-limit client %r (%s); using per-IP keys", name, exc)
        return frozenset()
    # sockaddr[0] is the address string for both AF_INET and AF_INET6; str() only
    # narrows the stdlib's wider sockaddr type.
    return frozenset(str(info[4][0]) for info in infos)


class ClientRegistry:
    """Resolves a peer IP to the ``ClientRule`` that covers it (first match wins)."""

    def __init__(
        self,
        rules: Iterable[ClientRule],
        resolver: Callable[[str], frozenset[str]] = resolve_hostname,
        ttl: float = RESOLVE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._rules = list(rules)
        self._resolver = resolver
        self._ttl = ttl
        self._clock = clock
        self._cache: dict[str, tuple[float, frozenset[str]]] = {}
        self._lock = threading.Lock()

    def __bool__(self) -> bool:
        return bool(self._rules)

    @property
    def rules(self) -> list[ClientRule]:
        return list(self._rules)

    def match(self, peer_ip: str | None) -> ClientRule | None:
        if not self._rules or not peer_ip:
            return None
        try:
            address: IPAddress = ipaddress.ip_address(peer_ip)
        except ValueError:
            return None  # not an IP at all (e.g. a test client's synthetic host)
        # uvicorn on a dual-stack socket reports v4 peers as ::ffff:a.b.c.d;
        # compare in v4 form so DNS answers (plain A records) still match.
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        for rule in self._rules:
            if rule.network is not None:
                if address in rule.network:
                    return rule
            elif str(address) in self._addresses(rule.name):
                return rule
        return None

    def _addresses(self, name: str) -> frozenset[str]:
        now = self._clock()
        with self._lock:
            cached = self._cache.get(name)
            if cached is not None and cached[0] > now:
                return cached[1]
        # Resolve outside the lock: a slow DNS answer must not stall requests
        # matching other rules. A duplicate concurrent lookup is harmless.
        addresses = self._resolver(name)
        with self._lock:
            self._cache[name] = (now + self._ttl, addresses)
        return addresses


def registry_from_env(env_var: str = "RATE_LIMIT_CLIENTS") -> ClientRegistry:
    return ClientRegistry(parse_client_rules(os.environ.get(env_var)))

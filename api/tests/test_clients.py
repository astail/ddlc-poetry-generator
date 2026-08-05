"""Name-based caller identification (RATE_LIMIT_CLIENTS)."""

from app.clients import ClientRegistry, parse_client_rules, resolve_hostname


def _registry(spec, addresses=None, **kwargs):
    """Registry over `spec` with DNS stubbed by a name -> addresses mapping."""
    table = addresses or {}
    return ClientRegistry(
        parse_client_rules(spec),
        resolver=lambda name: frozenset(table.get(name, ())),
        **kwargs,
    )


# ---- parsing -----------------------------------------------------------------


def test_parses_names_with_and_without_limits():
    rules = parse_client_rules("frontend=120, cloudflared ,10.8.0.0/24=5")
    assert [(r.name, r.max_per_min) for r in rules] == [
        ("frontend", 120),
        ("cloudflared", None),
        ("10.8.0.0/24", 5),
    ]
    # Only the CIDR entry is address-matched; the others are resolved by name.
    assert [r.network is None for r in rules] == [True, True, False]


def test_ignores_blank_and_malformed_entries():
    rules = parse_client_rules(" , frontend=abc, =5, worker=0, worker=-1, api=10 ")
    assert [(r.name, r.max_per_min) for r in rules] == [("api", 10)]


def test_empty_config_is_inert():
    assert parse_client_rules(None) == []
    assert not _registry("")
    assert _registry("").match("10.0.0.1") is None


# ---- matching ----------------------------------------------------------------


def test_matches_a_service_name_via_dns():
    reg = _registry("frontend=120", {"frontend": ["172.18.0.5"]})
    rule = reg.match("172.18.0.5")
    assert rule is not None
    assert (rule.name, rule.max_per_min) == ("frontend", 120)
    assert reg.match("172.18.0.9") is None  # some other container


def test_matches_every_replica_of_a_scaled_service():
    reg = _registry("frontend", {"frontend": ["172.18.0.5", "172.18.0.6"]})
    assert reg.match("172.18.0.5").name == "frontend"
    assert reg.match("172.18.0.6").name == "frontend"


def test_matches_ip_and_cidr_entries():
    reg = _registry("10.8.0.0/24=5,192.168.1.7")
    assert reg.match("10.8.0.42").name == "10.8.0.0/24"
    assert reg.match("192.168.1.7").name == "192.168.1.7"
    assert reg.match("192.168.1.8") is None


def test_first_matching_rule_wins():
    reg = _registry("frontend=120,10.0.0.0/8=5", {"frontend": ["10.0.0.3"]})
    assert reg.match("10.0.0.3").name == "frontend"
    assert reg.match("10.0.0.4").name == "10.0.0.0/8"


def test_ipv4_mapped_ipv6_peer_matches_an_a_record():
    # uvicorn on a dual-stack socket reports v4 peers as ::ffff:a.b.c.d.
    reg = _registry("frontend", {"frontend": ["172.18.0.5"]})
    assert reg.match("::ffff:172.18.0.5").name == "frontend"


def test_ipv6_entries_match():
    reg = _registry("frontend", {"frontend": ["fd00::5"]})
    assert reg.match("fd00::5").name == "frontend"
    assert reg.match("fd00::6") is None


def test_non_ip_peer_never_matches():
    reg = _registry("frontend", {"frontend": ["172.18.0.5"]})
    assert reg.match("testclient") is None
    assert reg.match(None) is None


def test_unresolvable_name_matches_nothing_instead_of_raising():
    # A service that isn't up yet (or a typo) must degrade to per-IP keying, not
    # 500 the request. resolve_hostname turns the OSError into "no addresses".
    assert resolve_hostname("no-such-service.invalid") == frozenset()
    reg = _registry("no-such-service.invalid")
    assert reg.match("172.18.0.5") is None


# ---- resolution caching ------------------------------------------------------


def test_dns_is_cached_for_the_ttl_then_refreshed():
    calls = []
    answers = {"frontend": ["172.18.0.5"]}
    now = [0.0]

    def resolver(name):
        calls.append(name)
        return frozenset(answers[name])

    reg = ClientRegistry(
        parse_client_rules("frontend"),
        resolver=resolver,
        ttl=30.0,
        clock=lambda: now[0],
    )

    assert reg.match("172.18.0.5").name == "frontend"
    now[0] = 29.0
    assert reg.match("172.18.0.5").name == "frontend"
    assert len(calls) == 1  # served from cache

    # The container is recreated with a new IP; after the TTL we pick it up.
    answers["frontend"] = ["172.18.0.9"]
    now[0] = 31.0
    assert reg.match("172.18.0.5") is None
    assert reg.match("172.18.0.9").name == "frontend"
    assert len(calls) == 2


def test_failed_lookup_is_cached_so_dns_is_not_hammered():
    calls = []

    def resolver(name):
        calls.append(name)
        return frozenset()  # what the real resolver returns on OSError

    reg = ClientRegistry(parse_client_rules("frontend"), resolver=resolver, clock=lambda: 0.0)
    for _ in range(5):
        assert reg.match("172.18.0.5") is None
    assert len(calls) == 1

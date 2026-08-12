import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

import services.mfa.app.manager as manager_module
from services.mfa.app.manager import (
    MFARequestAlreadyDecided,
    MFARequestExpired,
    MFARequestNotFound,
    MFAManager,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.set_calls = []

    def set(
        self,
        key,
        value,
        ex=None,
    ):
        self.values[key] = value

        if ex is not None:
            self.ttls[key] = ex

        self.set_calls.append(
            (
                key,
                value,
                ex,
            )
        )

        return True

    def get(self, key):
        return self.values.get(key)

    def ttl(self, key):
        return self.ttls.get(
            key,
            -1,
        )

    def scan_iter(self, match=None):
        for key in list(
            self.values.keys()
        ):
            yield key


def fixed_now():
    return datetime(
        2026,
        8,
        12,
        12,
        0,
        tzinfo=timezone.utc,
    )


def make_manager(
    monkeypatch,
    timeout=45,
):
    redis = FakeRedis()

    manager = MFAManager(
        redis,
        timeout_seconds=timeout,
    )

    monkeypatch.setattr(
        manager,
        "_now",
        fixed_now,
    )

    monkeypatch.setattr(
        manager_module.secrets,
        "token_urlsafe",
        lambda n: "req-fixed",
    )

    return manager, redis


def test_key():
    manager = MFAManager(
        FakeRedis()
    )

    assert (
        manager._key("abc")
        == "mfa:request:abc"
    )


def test_create_request_full(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch,
        timeout=45,
    )

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
        country="France",
        country_code="FR",
        city="Paris",
        isp="ISP",
    )

    assert request.request_id == "req-fixed"
    assert request.status == "pending"
    assert request.created_at == fixed_now()

    assert request.expires_at == (
        fixed_now()
        + timedelta(seconds=45)
    )

    assert request.country == "France"
    assert request.country_code == "FR"
    assert request.city == "Paris"
    assert request.isp == "ISP"

    key = "mfa:request:req-fixed"

    assert key in redis.values
    assert redis.ttls[key] == 105

    stored = json.loads(
        redis.values[key]
    )

    assert (
        stored["request_id"]
        == "req-fixed"
    )


def test_get_request_not_found(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    with pytest.raises(
        MFARequestNotFound,
        match="introuvable",
    ):
        manager.get_request(
            "missing"
        )


def test_get_request_bytes(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    key = manager._key(
        request.request_id
    )

    redis.values[key] = (
        redis.values[key].encode()
    )

    result = manager.get_request(
        request.request_id
    )

    assert (
        result.request_id
        == request.request_id
    )


def test_pending_request_auto_expires(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    monkeypatch.setattr(
        manager,
        "_now",
        lambda:
            fixed_now()
            + timedelta(minutes=5),
    )

    result = manager.get_request(
        request.request_id
    )

    assert result.status == "expired"

    stored = json.loads(
        redis.values[
            manager._key(
                request.request_id
            )
        ]
    )

    assert (
        stored["status"]
        == "expired"
    )


@pytest.mark.parametrize(
    "ttl",
    [
        None,
        0,
        -1,
    ],
)
def test_save_invalid_ttl_falls_back_to_60(
    monkeypatch,
    ttl,
):
    manager, redis = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    key = manager._key(
        request.request_id
    )

    if ttl is None:
        redis.ttls.pop(
            key,
            None,
        )

        redis.ttl = (
            lambda k: None
        )

    else:
        redis.ttls[key] = ttl

    manager._save(request)

    assert (
        redis.set_calls[-1][2]
        == 60
    )


def test_save_keeps_positive_ttl(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    key = manager._key(
        request.request_id
    )

    redis.ttls[key] = 33

    manager._save(request)

    assert (
        redis.set_calls[-1][2]
        == 33
    )


def test_approve_success(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    result = manager.approve(
        request.request_id,
        source="panel",
    )

    assert result.status == "approved"
    assert (
        result.decision_source
        == "panel"
    )
    assert (
        result.decided_at
        == fixed_now()
    )


def test_approve_expired(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    monkeypatch.setattr(
        manager,
        "_now",
        lambda:
            fixed_now()
            + timedelta(minutes=5),
    )

    with pytest.raises(
        MFARequestExpired
    ):
        manager.approve(
            request.request_id
        )


def test_approve_already_decided(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    manager.approve(
        request.request_id
    )

    with pytest.raises(
        MFARequestAlreadyDecided,
        match="approved",
    ):
        manager.approve(
            request.request_id
        )


def test_deny_success(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    result = manager.deny(
        request.request_id,
        source="telegram",
    )

    assert result.status == "denied"
    assert (
        result.decision_source
        == "telegram"
    )


def test_deny_expired(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    monkeypatch.setattr(
        manager,
        "_now",
        lambda:
            fixed_now()
            + timedelta(minutes=5),
    )

    with pytest.raises(
        MFARequestExpired
    ):
        manager.deny(
            request.request_id
        )


def test_deny_already_decided(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    manager.deny(
        request.request_id
    )

    with pytest.raises(
        MFARequestAlreadyDecided,
        match="denied",
    ):
        manager.deny(
            request.request_id
        )


def test_cancel_success(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    result = manager.cancel(
        request.request_id,
        source="system-test",
    )

    assert result.status == "cancelled"
    assert (
        result.decision_source
        == "system-test"
    )


def test_cancel_already_decided(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "admin",
        "1.2.3.4",
    )

    manager.approve(
        request.request_id
    )

    with pytest.raises(
        MFARequestAlreadyDecided
    ):
        manager.cancel(
            request.request_id
        )


def test_list_requests_sorted(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch
    )

    first = manager.create_request(
        "a",
        "1.1.1.1",
    )

    monkeypatch.setattr(
        manager,
        "_now",
        lambda:
            fixed_now()
            + timedelta(seconds=1),
    )

    monkeypatch.setattr(
        manager_module.secrets,
        "token_urlsafe",
        lambda n: "req-second",
    )

    second = manager.create_request(
        "b",
        "2.2.2.2",
    )

    result = manager.list_requests()

    assert (
        result[0].request_id
        == second.request_id
    )

    assert (
        result[1].request_id
        == first.request_id
    )


def test_list_requests_status_filter(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    first = manager.create_request(
        "a",
        "1.1.1.1",
    )

    manager.approve(
        first.request_id
    )

    monkeypatch.setattr(
        manager_module.secrets,
        "token_urlsafe",
        lambda n: "req-second",
    )

    manager.create_request(
        "b",
        "2.2.2.2",
    )

    result = manager.list_requests(
        status="approved"
    )

    assert len(result) == 1
    assert (
        result[0].status
        == "approved"
    )


def test_list_requests_limit(
    monkeypatch,
):
    manager, _ = make_manager(
        monkeypatch
    )

    manager.create_request(
        "a",
        "1.1.1.1",
    )

    monkeypatch.setattr(
        manager_module.secrets,
        "token_urlsafe",
        lambda n: "req-second",
    )

    manager.create_request(
        "b",
        "2.2.2.2",
    )

    assert len(
        manager.list_requests(
            limit=1
        )
    ) == 1


def test_list_requests_bytes_key(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch
    )

    request = manager.create_request(
        "a",
        "1.1.1.1",
    )

    key = manager._key(
        request.request_id
    )

    #
    # Un vrai redis-py peut retourner les clés
    # de SCAN sous forme bytes, tout en permettant
    # ensuite un GET avec la clé str équivalente.
    #
    # On simule donc uniquement la sortie bytes
    # de scan_iter sans déplacer la valeur stockée.
    #
    monkeypatch.setattr(
        redis,
        "scan_iter",
        lambda match=None: [
            key.encode("utf-8")
        ],
    )

    result = manager.list_requests()

    assert len(result) == 1

    assert (
        result[0].request_id
        == request.request_id
    )


def test_list_requests_skips_bad_request(
    monkeypatch,
):
    manager, redis = make_manager(
        monkeypatch
    )

    redis.values[
        "mfa:request:bad"
    ] = "{bad-json"

    # get_request() lève ici JSONDecodeError,
    # qui n'est PAS MFAError dans le code actuel.
    # On utilise donc une vraie MFAError via monkeypatch.
    original = manager.get_request

    def fake_get(request_id):
        if request_id == "bad":
            raise MFARequestNotFound(
                "bad"
            )

        return original(
            request_id
        )

    monkeypatch.setattr(
        manager,
        "get_request",
        fake_get,
    )

    assert (
        manager.list_requests()
        == []
    )

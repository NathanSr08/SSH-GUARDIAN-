import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from services.mfa.app.manager import (
    MFAManager,
    MFARequestAlreadyDecided,
    MFARequestExpired,
    MFARequestNotFound,
)


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.ttls = {}

    def set(
        self,
        key,
        value,
        ex=None,
    ):
        self.data[key] = value

        if ex is not None:
            self.ttls[key] = ex

        return True

    def get(
        self,
        key,
    ):
        return self.data.get(
            key
        )

    def ttl(
        self,
        key,
    ):
        return self.ttls.get(
            key,
            -1,
        )


def make_manager(
    timeout=45,
):
    return MFAManager(
        FakeRedis(),
        timeout_seconds=timeout,
    )


def test_mfa_request_creation():
    manager = make_manager()

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
        country="France",
        country_code="FR",
        city="Paris",
        isp="Example ISP",
    )

    assert request.request_id
    assert request.username == "admin"
    assert request.ip == "1.2.3.4"
    assert request.status == "pending"

    assert request.country == "France"
    assert request.country_code == "FR"
    assert request.city == "Paris"
    assert request.isp == "Example ISP"


def test_mfa_request_is_saved():
    redis = FakeRedis()

    manager = MFAManager(
        redis,
        timeout_seconds=45,
    )

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    key = (
        f"mfa:request:"
        f"{request.request_id}"
    )

    assert key in redis.data

    payload = json.loads(
        redis.data[key]
    )

    assert (
        payload["request_id"]
        == request.request_id
    )

    assert (
        payload["status"]
        == "pending"
    )


def test_mfa_request_can_be_read():
    manager = make_manager()

    created = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    loaded = manager.get_request(
        created.request_id
    )

    assert (
        loaded.request_id
        == created.request_id
    )

    assert loaded.status == "pending"


def test_mfa_request_approval():
    manager = make_manager()

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    approved = manager.approve(
        request.request_id,
        source="telegram",
    )

    assert (
        approved.status
        == "approved"
    )

    assert (
        approved.decision_source
        == "telegram"
    )

    assert (
        approved.decided_at
        is not None
    )


def test_mfa_request_denial():
    manager = make_manager()

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    denied = manager.deny(
        request.request_id,
        source="telegram",
    )

    assert denied.status == "denied"

    assert (
        denied.decision_source
        == "telegram"
    )


def test_mfa_double_approval_is_rejected():
    manager = make_manager()

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    manager.approve(
        request.request_id
    )

    with pytest.raises(
        MFARequestAlreadyDecided
    ):
        manager.approve(
            request.request_id
        )


def test_mfa_approve_after_denial_is_rejected():
    manager = make_manager()

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    manager.deny(
        request.request_id
    )

    with pytest.raises(
        MFARequestAlreadyDecided
    ):
        manager.approve(
            request.request_id
        )


def test_mfa_unknown_request_is_rejected():
    manager = make_manager()

    with pytest.raises(
        MFARequestNotFound
    ):
        manager.get_request(
            "does-not-exist"
        )


def test_mfa_expired_request_is_detected():
    manager = make_manager(
        timeout=45
    )

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    key = manager._key(
        request.request_id
    )

    payload = json.loads(
        manager.redis.data[key]
    )

    payload["expires_at"] = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            seconds=5
        )
    ).isoformat()

    manager.redis.data[key] = (
        json.dumps(
            payload
        )
    )

    loaded = manager.get_request(
        request.request_id
    )

    assert loaded.status == "expired"


def test_mfa_expired_request_cannot_be_approved():
    manager = make_manager()

    request = manager.create_request(
        username="admin",
        ip="1.2.3.4",
    )

    key = manager._key(
        request.request_id
    )

    payload = json.loads(
        manager.redis.data[key]
    )

    payload["expires_at"] = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            seconds=5
        )
    ).isoformat()

    manager.redis.data[key] = (
        json.dumps(
            payload
        )
    )

    with pytest.raises(
        MFARequestExpired
    ):
        manager.approve(
            request.request_id
        )

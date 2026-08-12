from types import SimpleNamespace

import services.mfa.app.service as service_module
from services.mfa.app.service import MFAService


class FakeRequest:
    def __init__(
        self,
        request_id="req-1",
        username="admin",
        ip="203.0.113.30",
        status="pending",
        country=None,
        country_code=None,
        city=None,
        isp=None,
    ):
        self.request_id = request_id
        self.username = username
        self.ip = ip
        self.status = status
        self.country = country
        self.country_code = country_code
        self.city = city
        self.isp = isp

    def to_dict(self):
        return {
            "request_id":
                self.request_id,
            "username":
                self.username,
            "ip":
                self.ip,
            "status":
                self.status,
            "country":
                self.country,
            "country_code":
                self.country_code,
            "city":
                self.city,
            "isp":
                self.isp,
        }


class FakeManager:
    def __init__(self):
        self.created = []
        self.approved = []
        self.denied = []

    def create_request(self, **kwargs):
        self.created.append(
            kwargs
        )

        return FakeRequest(
            username=kwargs["username"],
            ip=kwargs["ip"],
            country=kwargs.get(
                "country"
            ),
            country_code=kwargs.get(
                "country_code"
            ),
            city=kwargs.get(
                "city"
            ),
            isp=kwargs.get(
                "isp"
            ),
        )

    def approve(
        self,
        request_id,
        source="telegram",
    ):
        self.approved.append(
            (
                request_id,
                source,
            )
        )

        return FakeRequest(
            request_id=request_id,
            status="approved",
        )

    def deny(
        self,
        request_id,
        source="telegram",
    ):
        self.denied.append(
            (
                request_id,
                source,
            )
        )

        return FakeRequest(
            request_id=request_id,
            status="denied",
        )

    def get_request(
        self,
        request_id,
    ):
        return FakeRequest(
            request_id=request_id
        )


class FakeGeoIP:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def lookup(self, ip):
        self.calls.append(ip)

        if self.error:
            raise self.error

        return self.result


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(
        self,
        stream,
        payload,
    ):
        self.published.append(
            (
                stream,
                payload,
            )
        )

        return "1-0"


def make_service(
    geo=None,
):
    service = object.__new__(
        MFAService
    )

    service.bus = FakeBus()
    service.manager = FakeManager()
    service.geoip = (
        geo
        or FakeGeoIP({})
    )

    return service


def test_publish_event():
    service = make_service()

    request = FakeRequest()

    event_id = service.publish_event(
        "mfa.request.created",
        request,
    )

    assert event_id == "1-0"

    _, payload = (
        service.bus.published[0]
    )

    assert (
        payload["event_type"]
        == "mfa.request.created"
    )


def test_create_uses_provided_geo_without_lookup():
    geo = FakeGeoIP(
        {
            "country": "wrong",
        }
    )

    service = make_service(
        geo
    )

    request = service.create(
        "admin",
        "203.0.113.30",
        country="France",
        country_code="FR",
        city="Paris",
        isp="ISP",
    )

    assert geo.calls == []

    assert request.country == "France"
    assert request.city == "Paris"
    assert request.isp == "ISP"


def test_create_enriches_missing_geo():
    geo = FakeGeoIP(
        {
            "country": "France",
            "country_code": "FR",
            "city": "Paris",
            "isp": "Test ISP",
        }
    )

    service = make_service(
        geo
    )

    request = service.create(
        "admin",
        "203.0.113.30",
    )

    assert geo.calls == [
        "203.0.113.30"
    ]

    assert request.country == "France"
    assert request.country_code == "FR"
    assert request.city == "Paris"
    assert request.isp == "Test ISP"


def test_geoip_failure_does_not_break_mfa():
    service = make_service(
        FakeGeoIP(
            error=RuntimeError(
                "geo down"
            )
        )
    )

    request = service.create(
        "admin",
        "203.0.113.30",
    )

    assert request.username == "admin"

    assert (
        service.bus.published[-1][1][
            "event_type"
        ]
        == "mfa.request.created"
    )


def test_create_publishes_created_event():
    service = make_service()

    service.create(
        "admin",
        "203.0.113.30",
        country="France",
        city="Paris",
        isp="ISP",
    )

    assert (
        service.bus.published[-1][1][
            "event_type"
        ]
        == "mfa.request.created"
    )


def test_approve_publishes_event():
    service = make_service()

    result = service.approve(
        "req-1",
        source="panel",
    )

    assert result.status == "approved"

    assert (
        service.bus.published[-1][1][
            "event_type"
        ]
        == "mfa.request.approved"
    )


def test_deny_publishes_event():
    service = make_service()

    result = service.deny(
        "req-1",
        source="telegram",
    )

    assert result.status == "denied"

    assert (
        service.bus.published[-1][1][
            "event_type"
        ]
        == "mfa.request.denied"
    )


def test_get_delegates_to_manager():
    service = make_service()

    result = service.get(
        "req-123"
    )

    assert (
        result.request_id
        == "req-123"
    )

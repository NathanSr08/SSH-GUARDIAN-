from services.mfa.app.manager import (
    MFAManager,
)

from services.geoip.app.provider import (
    GeoIPProvider,
)

from shared.config.settings import Settings


class MFAService:
    def __init__(
        self,
        bus,
    ):
        self.bus = bus

        self.manager = MFAManager(
            bus.client,
            timeout_seconds=
                Settings.MFA_TIMEOUT_SECONDS,
        )

        #
        # On réutilise exactement le même provider
        # GeoIP que le pipeline SSH Guardian.
        #
        self.geoip = GeoIPProvider(
            bus
        )

    def publish_event(
        self,
        event_type: str,
        request,
    ):
        payload = request.to_dict()

        payload[
            "event_type"
        ] = event_type

        return self.bus.publish(
            Settings.MFA_EVENTS_STREAM,
            payload,
        )

    def create(
        self,
        username: str,
        ip: str,
        country=None,
        country_code=None,
        city=None,
        isp=None,
    ):
        #
        # Si le demandeur n'a pas déjà fourni
        # les informations GeoIP, on les récupère.
        #
        if not (
            country
            and city
            and isp
        ):
            try:
                geo = (
                    self.geoip.lookup(
                        ip
                    )
                    or {}
                )

                country = (
                    country
                    or geo.get(
                        "country"
                    )
                )

                country_code = (
                    country_code
                    or geo.get(
                        "country_code"
                    )
                )

                city = (
                    city
                    or geo.get(
                        "city"
                    )
                )

                isp = (
                    isp
                    or geo.get(
                        "isp"
                    )
                )

            except Exception as exc:
                #
                # Une panne GeoIP ne doit jamais
                # empêcher le MFA de fonctionner.
                #
                print(
                    "[MFA GEOIP ERROR] "
                    f"ip={ip} "
                    f"{exc}"
                )

        request = (
            self.manager.create_request(
                username=username,
                ip=ip,
                country=country,
                country_code=country_code,
                city=city,
                isp=isp,
            )
        )

        self.publish_event(
            "mfa.request.created",
            request,
        )

        return request

    def approve(
        self,
        request_id: str,
        source="telegram",
    ):
        request = (
            self.manager.approve(
                request_id,
                source=source,
            )
        )

        self.publish_event(
            "mfa.request.approved",
            request,
        )

        return request

    def deny(
        self,
        request_id: str,
        source="telegram",
    ):
        request = (
            self.manager.deny(
                request_id,
                source=source,
            )
        )

        self.publish_event(
            "mfa.request.denied",
            request,
        )

        return request

    def get(
        self,
        request_id: str,
    ):
        return (
            self.manager.get_request(
                request_id
            )
        )

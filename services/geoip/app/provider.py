import ipaddress
import json

import requests

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings


class GeoIPProvider:
    def __init__(self, bus: RedisBus):
        self.bus = bus

    def _cache_key(self, ip: str) -> str:
        return f"geoip:{ip}"

    def _unknown(self, ip: str, reason: str) -> dict:
        return {
            "ip": ip,
            "country": "Inconnu",
            "country_code": None,
            "city": "Inconnu",
            "region": None,
            "isp": "Inconnu",
            "org": None,
            "asn": None,
            "lat": None,
            "lon": None,
            "timezone": None,
            "geo_status": reason,
            "geo_cache": False,
        }

    def lookup(self, ip: str) -> dict:
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            return self._unknown(ip, "invalid_ip")

        if not parsed.is_global:
            return self._unknown(
                ip,
                "private_or_reserved",
            )

        key = self._cache_key(ip)

        cached = self.bus.client.get(key)

        if cached:
            try:
                data = json.loads(cached)
                data["geo_cache"] = True
                return data
            except json.JSONDecodeError:
                self.bus.client.delete(key)

        try:
            response = requests.get(
                f"http://ip-api.com/json/{ip}",
                params={
                    "fields": (
                        "status,message,query,"
                        "country,countryCode,"
                        "regionName,city,"
                        "lat,lon,timezone,"
                        "isp,org,as"
                    )
                },
                timeout=Settings.GEOIP_TIMEOUT,
            )

            response.raise_for_status()

            raw = response.json()

        except Exception as exc:
            return self._unknown(
                ip,
                f"provider_error:{type(exc).__name__}",
            )

        if raw.get("status") != "success":
            return self._unknown(
                ip,
                raw.get("message", "provider_failed"),
            )

        data = {
            "ip": ip,
            "country": raw.get("country") or "Inconnu",
            "country_code": raw.get("countryCode"),
            "city": raw.get("city") or "Inconnu",
            "region": raw.get("regionName"),
            "isp": raw.get("isp") or "Inconnu",
            "org": raw.get("org"),
            "asn": raw.get("as"),
            "lat": raw.get("lat"),
            "lon": raw.get("lon"),
            "timezone": raw.get("timezone"),
            "geo_status": "success",
            "geo_cache": False,
        }

        self.bus.client.setex(
            key,
            Settings.GEOIP_CACHE_TTL,
            json.dumps(
                data,
                ensure_ascii=False,
            ),
        )

        return data

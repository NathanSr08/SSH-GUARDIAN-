from dataclasses import dataclass
from datetime import datetime
from typing import Literal


MFAStatus = Literal[
    "pending",
    "approved",
    "denied",
    "expired",
    "cancelled",
]


@dataclass
class MFARequest:
    request_id: str
    username: str
    ip: str

    status: MFAStatus

    created_at: datetime
    expires_at: datetime

    country: str | None = None
    country_code: str | None = None
    city: str | None = None
    isp: str | None = None

    decided_at: datetime | None = None
    decision_source: str | None = None

    def to_dict(self) -> dict:
        return {
            "request_id":
                self.request_id,

            "username":
                self.username,

            "ip":
                self.ip,

            "status":
                self.status,

            "created_at":
                self.created_at.isoformat(),

            "expires_at":
                self.expires_at.isoformat(),

            "country":
                self.country,

            "country_code":
                self.country_code,

            "city":
                self.city,

            "isp":
                self.isp,

            "decided_at":
                (
                    self.decided_at.isoformat()
                    if self.decided_at
                    else None
                ),

            "decision_source":
                self.decision_source,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict,
    ) -> "MFARequest":

        decided_at = payload.get(
            "decided_at"
        )

        return cls(
            request_id=payload[
                "request_id"
            ],

            username=payload[
                "username"
            ],

            ip=payload[
                "ip"
            ],

            status=payload[
                "status"
            ],

            created_at=datetime.fromisoformat(
                payload["created_at"]
            ),

            expires_at=datetime.fromisoformat(
                payload["expires_at"]
            ),

            country=payload.get(
                "country"
            ),

            country_code=payload.get(
                "country_code"
            ),

            city=payload.get(
                "city"
            ),

            isp=payload.get(
                "isp"
            ),

            decided_at=(
                datetime.fromisoformat(
                    decided_at
                )
                if decided_at
                else None
            ),

            decision_source=payload.get(
                "decision_source"
            ),
        )

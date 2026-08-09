from dataclasses import asdict, dataclass
from datetime import datetime
import json


@dataclass
class SSHEvent:
    event_type: str
    timestamp: datetime
    ip: str
    username: str | None = None
    message: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
        )

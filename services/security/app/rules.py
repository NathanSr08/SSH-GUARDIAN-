from dataclasses import dataclass


@dataclass
class SecurityRules:
    max_attempts: int = 3
    window_seconds: int = 86400
    ban_duration_seconds: int = 86400

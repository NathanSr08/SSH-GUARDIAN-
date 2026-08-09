import ipaddress
import subprocess

from shared.config.settings import Settings


class FirewallError(Exception):
    pass


class Firewall:
    def __init__(self):
        self.enabled = Settings.FIREWALL_ENABLED
        self.whitelist = Settings.WHITELIST

    def validate_ip(self, ip: str) -> str:
        try:
            return str(ipaddress.ip_address(ip))
        except ValueError as exc:
            raise FirewallError(f"Adresse IP invalide : {ip}") from exc

    def is_whitelisted(self, ip: str) -> bool:
        return ip in self.whitelist

    def ban(self, ip: str) -> dict:
        ip = self.validate_ip(ip)

        if self.is_whitelisted(ip):
            return {
                "status": "ignored",
                "reason": "whitelisted",
                "ip": ip,
            }

        if not self.enabled:
            return {
                "status": "dry_run",
                "action": "ban",
                "ip": ip,
            }

        check = subprocess.run(
            [
                "iptables",
                "-C",
                "INPUT",
                "-s",
                ip,
                "-j",
                "DROP",
            ],
            capture_output=True,
            text=True,
        )

        if check.returncode != 0:
            result = subprocess.run(
                [
                    "iptables",
                    "-I",
                    "INPUT",
                    "1",
                    "-s",
                    ip,
                    "-j",
                    "DROP",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise FirewallError(result.stderr.strip())

        return {
            "status": "banned",
            "ip": ip,
        }

    def unban(self, ip: str) -> dict:
        ip = self.validate_ip(ip)

        if not self.enabled:
            return {
                "status": "dry_run",
                "action": "unban",
                "ip": ip,
            }

        while True:
            result = subprocess.run(
                [
                    "iptables",
                    "-D",
                    "INPUT",
                    "-s",
                    ip,
                    "-j",
                    "DROP",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                break

        return {
            "status": "unbanned",
            "ip": ip,
        }

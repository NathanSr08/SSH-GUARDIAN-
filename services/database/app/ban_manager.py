from services.database.app.repository import DatabaseRepository
from services.firewall.app.firewall import Firewall, FirewallError


class BanManager:
    def __init__(
        self,
        repository: DatabaseRepository,
        firewall: Firewall,
    ):
        self.repository = repository
        self.firewall = firewall

    def cleanup_expired_bans(self):
        expired = self.repository.get_expired_bans()

        results = []

        for ban_id, ip in expired:
            try:
                firewall_result = self.firewall.unban(ip)
                self.repository.mark_unbanned(ban_id)

                results.append(
                    {
                        "ip": ip,
                        "status": "expired",
                        "firewall": firewall_result,
                    }
                )

            except FirewallError as exc:
                results.append(
                    {
                        "ip": ip,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        return results

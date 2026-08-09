import subprocess
from datetime import datetime, timezone

from shared.config.settings import Settings
from services.firewall.app.firewall import Firewall, FirewallError


COUNTRY_SCRIPT = str(Settings.COUNTRY_SCRIPT)


class CountryManager:
    def __init__(self, bus, control_manager):
        self.bus = bus
        self.control_manager = control_manager
        self.firewall = Firewall()

    def country_code(self, value: str) -> str | None:
        return self.control_manager.country_code(value)

    def block(self, country: str) -> str:
        code = self.country_code(country)

        if not code:
            return "❌ Pays inconnu."

        result = subprocess.run(
            [
                COUNTRY_SCRIPT,
                "block",
                code,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return (
                f"❌ Erreur pendant le blocage de "
                f"<b>{code.upper()}</b>.\n"
                f"<pre>{result.stderr}</pre>"
            )

        self.bus.publish(
            Settings.FIREWALL_EVENTS_STREAM,
            {
                "event_type": "security.country.blocked",
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "country_code": code.upper(),
                "reason": "manual_country_block",
            },
        )

        return (
            f"🛡 Pays <b>{code.upper()}</b> bloqué.\n\n"
            "Toute nouvelle connexion détectée depuis "
            "ce pays sera bloquée automatiquement."
        )

    def get_country_banned_ips(
        self,
        country_code: str,
    ) -> list[str]:
        """
        Retourne uniquement les IP actuellement marquées
        par Security comme bannies à cause d'un pays.
        """

        wanted = country_code.lower()

        ips = set()

        for key in self.bus.client.scan_iter(
            match="security:blocked-country:*",
            count=500,
        ):
            try:
                value = self.bus.client.get(key)

                if not value:
                    continue

                if str(value).lower() != wanted:
                    continue

                ip = str(key).split(
                    "security:blocked-country:",
                    1,
                )[1]

                if ip:
                    ips.add(ip)

            except Exception:
                continue

        return sorted(ips)

    def unblock(self, country: str) -> str:
        code = self.country_code(country)

        if not code:
            return "❌ Pays inconnu."

        #
        # IMPORTANT :
        # récupérer les IP AVANT de supprimer les marqueurs.
        #
        ips = self.get_country_banned_ips(
            code
        )

        #
        # 1. Retirer immédiatement le pays
        #    de la politique de blocage.
        #
        result = subprocess.run(
            [
                COUNTRY_SCRIPT,
                "unblock",
                code,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return (
                f"❌ Impossible de débloquer "
                f"<b>{code.upper()}</b>.\n"
                f"<pre>{result.stderr}</pre>"
            )

        unbanned = []
        failed = []

        #
        # 2. Débannir toutes les IP actuellement
        #    bloquées PAR CETTE politique pays.
        #
        for ip in ips:
            try:
                firewall_result = (
                    self.firewall.unban(ip)
                )

                status = firewall_result.get(
                    "status"
                )

                if status == "unbanned":
                    unbanned.append(ip)

                    #
                    # Le ban pays n'existe plus :
                    # supprimer également l'état Redis.
                    #
                    self.bus.client.delete(
                        f"security:blocked-country:{ip}"
                    )

                    #
                    # Publier l'événement pour Storage,
                    # Telegram et futur dashboard.
                    #
                    self.bus.publish(
                        Settings.FIREWALL_EVENTS_STREAM,
                        {
                            "event_type":
                                "firewall.ip.unbanned",

                            "timestamp":
                                datetime.now(
                                    timezone.utc
                                ).isoformat(),

                            "ip":
                                ip,

                            "reason":
                                "country_unblocked",

                            "country_code":
                                code.upper(),

                            "firewall_result":
                                firewall_result,
                        },
                    )

                else:
                    failed.append(
                        {
                            "ip": ip,
                            "result":
                                firewall_result,
                        }
                    )

            except FirewallError as exc:
                failed.append(
                    {
                        "ip": ip,
                        "error": str(exc),
                    }
                )

            except Exception as exc:
                failed.append(
                    {
                        "ip": ip,
                        "error": str(exc),
                    }
                )

        #
        # 3. Nettoyage de sécurité :
        #    même si une règle iptables avait déjà disparu,
        #    on ne veut pas laisser une ancienne clé Redis.
        #
        for ip in ips:
            self.bus.client.delete(
                f"security:blocked-country:{ip}"
            )

        lines = [
            f"🔓 Pays <b>{code.upper()}</b> débloqué."
        ]

        if unbanned:
            lines.extend(
                [
                    "",
                    (
                        f"✅ <b>{len(unbanned)} "
                        "IP(s) débannie(s)</b>"
                    ),
                ]
            )

            for ip in unbanned[:30]:
                lines.append(
                    f"• <code>{ip}</code>"
                )

            if len(unbanned) > 30:
                lines.append(
                    f"• ... +{len(unbanned) - 30}"
                )

        elif ips:
            lines.extend(
                [
                    "",
                    (
                        "⚠️ Des IP étaient associées au pays, "
                        "mais aucune règle firewall active "
                        "n'a été supprimée."
                    ),
                ]
            )

        else:
            lines.extend(
                [
                    "",
                    (
                        "ℹ️ Aucune IP actuellement bannie "
                        "à cause de ce pays."
                    ),
                ]
            )

        if failed:
            lines.extend(
                [
                    "",
                    (
                        f"⚠️ {len(failed)} erreur(s) "
                        "pendant le déban."
                    ),
                ]
            )

        self.bus.publish(
            Settings.FIREWALL_EVENTS_STREAM,
            {
                "event_type": "security.country.unblocked",
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "country_code": code.upper(),
                "reason": "manual_country_unblock",
                "unbanned_count": len(unbanned),
            },
        )

        return "\n".join(lines)

    def countries(self) -> str:
        result = subprocess.run(
            [
                COUNTRY_SCRIPT,
                "list",
            ],
            capture_output=True,
            text=True,
        )

        countries = [
            country.strip()
            for country
            in result.stdout.splitlines()
            if country.strip()
        ]

        if not countries:
            return "📜 Aucun pays bloqué."

        lines = [
            "📜 <b>Pays bloqués</b>",
            "",
        ]

        for country in countries:
            lines.append(
                f"• {country.upper()}"
            )

        return "\n".join(lines)

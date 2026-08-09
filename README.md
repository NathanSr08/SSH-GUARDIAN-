<div align="center">

# SSH Guardian V2

### Real-time SSH monitoring, threat detection and automated response

**A lightweight Security Operations Center for Linux SSH infrastructure.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Debian%20%7C%20Ubuntu-FCC624?logo=linux&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-Services-000000?logo=linux&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)

<br>

**Monitor · Detect · Enrich · Block · Notify · Investigate**

</div>

---

## Overview

SSH Guardian V2 is a modular security platform designed to monitor and protect SSH services in real time.

Instead of operating as a single monolithic script, SSH Guardian uses independent services connected through **Redis Streams**.

Incoming SSH activity is collected from the Linux journal, normalized, enriched with GeoIP information, analyzed by the security engine, persisted in SQLite and exposed through Telegram, an HTTP API and a Web dashboard.

When malicious activity reaches the configured threshold, SSH Guardian can automatically instruct the firewall service to block the offending address.

```text
OpenSSH / journald
        │
        ▼
    Collector
        │
        │ ssh.events
        ▼
      Redis
        │
        ▼
      GeoIP
        │
        │ ssh.events.enriched
        ▼
      Redis
        │
        ├──────────────► Storage ─────► SQLite
        │
        ├──────────────► Telegram
        │
        └──────────────► Security
                              │
                              │ security.actions
                              ▼
                           Firewall
                              │
                              ▼
                       Linux firewall

                  SQLite / Control
                         │
                         ▼
                        API
                         │
                         ▼
                    Web Panel
```

---

## Key features

| Area | Capability |
|---|---|
| 🔍 Monitoring | Real-time SSH event monitoring through `journald` |
| 🚨 Detection | Failed authentication and suspicious connection detection |
| 🔢 Attempts | Per-IP attempt tracking and automatic threshold handling |
| 🌍 GeoIP | Country, ISO country code, city and ISP enrichment |
| 🔥 Firewall | Automatic IP banning and unbanning |
| 🌐 Country control | Automatic blocking of connections originating from configured countries |
| 🛡️ Whitelist | Protection of trusted administrative IP addresses |
| 📱 Telegram | Real-time security notifications and remote administration |
| 💻 Sessions | Active SSH session discovery and management |
| 📡 Streaming | Live/recorded SSH session inspection where supported |
| 🗄️ Storage | Persistent event history using SQLite |
| ⚡ Event bus | Decoupled service communication through Redis Streams |
| 🔌 API | HTTP API for statistics, events and administration |
| 🖥️ Dashboard | Web-based Security Operations Center |
| 🧪 Testing | Automated tests with pytest |
| ⚙️ Services | Production deployment through systemd |

---

## Security workflow

SSH Guardian processes events through several independent stages.

```text
SSH connection
     │
     ▼
Collector detects event
     │
     ▼
GeoIP enrichment
     │
     ▼
Security Engine
     │
     ├── Trusted IP ───────────────► Ignore
     │
     ├── Normal activity ──────────► Monitor
     │
     ├── Failed attempt ───────────► Increment counter
     │
     ├── Blocked country ──────────► Ban
     │
     └── Threshold reached ────────► Ban
                                         │
                                         ▼
                                      Firewall
```

The default policy can be configured to ban an address after three failed attempts.

Example:

```text
Attempt 1/3 → monitored
Attempt 2/3 → monitored
Attempt 3/3 → banned
```

---

## Project architecture

```text
ssh-guardian-v2/
│
├── services/
│   ├── collector/        SSH/journald event collection
│   ├── geoip/            IP geolocation enrichment
│   ├── security/         Detection and security decisions
│   ├── firewall/         Firewall enforcement
│   ├── storage/          Persistent event storage
│   ├── control/          Administrative operations
│   ├── telegram/         Telegram Bot interface
│   ├── api/              HTTP API
│   └── panel/            Web dashboard
│
├── shared/
│   ├── bus/              Redis communication
│   ├── config/           Shared configuration
│   └── events/           Event models
│
├── scripts/              Development and maintenance scripts
├── tests/                Automated test suite
├── data/                 SQLite database
├── logs/                 Development logs
├── run/                  Runtime PID files
│
├── install.sh            Automated installation
├── uninstall.sh          Automated removal
├── .env.example          Configuration template
├── requirements.txt      Python dependencies
└── README.md
```

---

## Requirements

SSH Guardian is intended for Linux servers using OpenSSH.

Recommended environment:

```text
Debian / Ubuntu
Python 3.11+
OpenSSH
systemd
Redis
SQLite
iptables / compatible firewall environment
```

Root privileges are required for installation and firewall operations.

---

## Quick installation

Clone or copy the project onto the server, then enter the project directory.

```bash
cd ssh-guardian-v2
```

Make the installer executable:

```bash
chmod +x install.sh
```

Run:

```bash
sudo ./install.sh
```

The installer is responsible for preparing the host, installing dependencies, creating required directories and configuring SSH Guardian services.

After installation, configure the environment before enabling real firewall enforcement.

---

## Environment configuration

SSH Guardian uses a `.env` file for machine-specific configuration and secrets.

A safe template is provided:

```text
.env.example
```

Create your local configuration:

```bash
cp .env.example .env
nano .env
```

The real `.env` must **never be committed to Git**.

Typical configuration:

```env
SG_STATE_DIR=/etc/ssh-guardian
SG_SESSION_LOG_DIR=/var/log/ssh_recorder

SG_REDIS_URL=redis://127.0.0.1:6379/0

SG_MAX_ATTEMPTS=3
SG_BAN_DURATION_SECONDS=86400

SG_WHITELIST=127.0.0.1,::1

SG_FIREWALL_ENABLED=false

SG_TELEGRAM_ENABLED=false
SG_TELEGRAM_TOKEN=
SG_TELEGRAM_CHAT_ID=

SG_API_HOST=127.0.0.1
SG_API_PORT=8080

SG_PANEL_HOST=127.0.0.1
SG_PANEL_PORT=3000
SG_PANEL_API_URL=http://127.0.0.1:8080
SG_PANEL_TOKEN=
```

---

## Security configuration

### Attempt threshold

```env
SG_MAX_ATTEMPTS=3
```

With the default value:

```text
1st failure → monitor
2nd failure → monitor
3rd failure → ban
```

### Ban duration

```env
SG_BAN_DURATION_SECONDS=86400
```

Common values:

| Duration | Seconds |
|---|---:|
| 1 hour | `3600` |
| 6 hours | `21600` |
| 12 hours | `43200` |
| 24 hours | `86400` |

### Whitelist

Trusted addresses can be configured with:

```env
SG_WHITELIST=127.0.0.1,::1
```

Multiple addresses are separated by commas:

```env
SG_WHITELIST=127.0.0.1,::1,203.0.113.10
```

> **Important:** add your administration IP to the whitelist before enabling real firewall enforcement.

### Firewall mode

For testing:

```env
SG_FIREWALL_ENABLED=false
```

This allows the detection pipeline to operate without actually blocking addresses.

For production enforcement:

```env
SG_FIREWALL_ENABLED=true
```

Only enable this after validating your whitelist and access configuration.

---

## Telegram integration

SSH Guardian includes a Telegram Bot interface for notifications and administrative commands.

### Create the bot

Open Telegram and start a conversation with **@BotFather**.

Send:

```text
/newbot
```

Choose a display name, for example:

```text
SSH Guardian
```

Then choose a unique bot username, for example:

```text
my_ssh_guardian_bot
```

BotFather will return an API token.

It looks similar to:

```text
1234567890:AA_EXAMPLE_TOKEN
```

Treat this token as a password.

### Configure the token

Edit `.env`:

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=YOUR_BOT_TOKEN
```

Do not place the real token in `.env.example`, documentation, commits or screenshots.

### Retrieve your Telegram Chat ID

First open your bot and send:

```text
/start
```

Then on the server:

```bash
TOKEN="YOUR_BOT_TOKEN"

curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | python3 -m json.tool
```

Look for:

```json
"chat": {
    "id": 123456789
}
```

Or retrieve it directly with `jq`:

```bash
TOKEN="YOUR_BOT_TOKEN"

curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | jq '.result[-1].message.chat.id'
```

Configure the result:

```env
SG_TELEGRAM_CHAT_ID=123456789
```

### Validate the bot token

```bash
TOKEN="YOUR_BOT_TOKEN"

curl -s \
  "https://api.telegram.org/bot${TOKEN}/getMe" \
  | python3 -m json.tool
```

A valid token returns:

```json
{
    "ok": true,
    "result": {
        "is_bot": true
    }
}
```

### Test notifications

```bash
TOKEN="YOUR_BOT_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

curl -s \
  -X POST \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  --data-urlencode "text=SSH Guardian is operational."
```

---

## Telegram commands

The Telegram interface provides access to the main administrative and investigation functions.

| Command | Purpose |
|---|---|
| `/stats` | Global security statistics |
| `/top` | Most active attacking IP addresses |
| `/topcountries` | Countries generating the most suspicious activity |
| `/search <IP>` | Search the history of an IP |
| `/bans` | Display active bans |
| `/unban <IP>` | Remove an IP ban |
| `/block <CC>` | Block a country |
| `/unblock <CC>` | Unblock a country |
| `/countries` | List blocked countries |
| `/sessions` | Display active SSH sessions |
| `/active` | Display active/live sessions |
| `/stream <PID>` | Inspect a streamable session |
| `/killsession <PID>` | Terminate a specific session |
| `/killallsessions` | Terminate managed remote sessions |

Example:

```text
/top
```

```text
🏆 Top IP addresses

1. 45.128.39.115 (Massamagrell, Spain) — 6
2. 82.80.219.126 (Maale Iron, Israel) — 4
3. 95.174.64.122 (Milan, Italy) — 3
```

Country blocking:

```text
/block it
```

Example response:

```text
🛡 Country IT blocked.

New addresses detected from this country
will automatically be banned.
```

Unblock:

```text
/unblock it
```

---

## Telegram security alerts

A failed connection can generate a notification similar to:

```text
🚨 SSH attempt failed

IP: 201.214.43.22
Location: Quillota, Chile
ISP: VTR BANDA ANCHA S.A.

Reason: connection closed before authentication

Attempts: 1/3
Remaining before ban: 2
```

After another failure:

```text
Attempts: 2/3
Remaining before ban: 1
```

Once the configured threshold is reached, the Security service emits a ban action and the Firewall service applies it.

---

## Country blocking

Countries are identified using ISO country codes.

Examples:

```text
IT → Italy
RU → Russia
CN → China
AZ → Azerbaijan
```

From Telegram:

```text
/block it
/unblock it
/countries
```

The command-line helper can also be used:

```bash
services/control/bin/country_blocker.sh block it
services/control/bin/country_blocker.sh unblock it
services/control/bin/country_blocker.sh list
```

A country block affects newly detected addresses from that country.

---

## Web dashboard

SSH Guardian includes a Web-based Security Operations Center.

The default configuration keeps it private:

```env
SG_PANEL_HOST=127.0.0.1
SG_PANEL_PORT=3000
```

The dashboard provides centralized visibility into information such as:

- service health;
- connection statistics;
- authentication failures;
- successful authentication;
- unique IP addresses;
- active bans;
- recent events;
- blocked countries;
- top attacking IP addresses;
- top attacking countries;
- active SSH sessions;
- administrative actions.

---

## Panel authentication

The dashboard is protected by:

```env
SG_PANEL_TOKEN=
```

A cryptographically random token can be generated with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Example:

```env
SG_PANEL_TOKEN=YOUR_RANDOM_ADMIN_TOKEN
```

The installation process may generate this token automatically when no token exists.

To display the currently configured token:

```bash
grep '^SG_PANEL_TOKEN=' .env
```

Only the value:

```bash
grep '^SG_PANEL_TOKEN=' .env | cut -d= -f2-
```

Keep this token private.

---

## Secure dashboard access

The recommended configuration does **not** expose the dashboard directly to the Internet.

Keep:

```env
SG_PANEL_HOST=127.0.0.1
```

Then establish an SSH tunnel from your workstation.

Example from Windows PowerShell:

```powershell
ssh -i C:\path\to\server.pem -N -L 3000:127.0.0.1:3000 admin@server.example.com
```

Keep the PowerShell session open and navigate to:

```text
http://127.0.0.1:3000
```

This forwards your local port `3000` through SSH to the private dashboard running on the server.

---

## HTTP API

The API is private by default:

```env
SG_API_HOST=127.0.0.1
SG_API_PORT=8080
```

Example requests:

```bash
curl http://127.0.0.1:8080/health
```

Top attacking IPs:

```bash
curl -s \
  http://127.0.0.1:8080/top \
  | python3 -m json.tool
```

Top countries:

```bash
curl -s \
  http://127.0.0.1:8080/topcountries \
  | python3 -m json.tool
```

---

## Redis event pipeline

Redis acts as the internal event bus.

Important streams include:

```text
ssh.events
ssh.events.enriched
security.actions
firewall.events
```

Check Redis:

```bash
redis-cli ping
```

Expected response:

```text
PONG
```

Inspect stream sizes:

```bash
redis-cli XLEN ssh.events
redis-cli XLEN ssh.events.enriched
redis-cli XLEN security.actions
redis-cli XLEN firewall.events
```

This architecture allows each service to operate independently while sharing normalized security events.

---

## Persistent storage

SSH Guardian stores its persistent security history in SQLite.

Default project database:

```text
data/guardian.db
```

Open it with:

```bash
sqlite3 data/guardian.db
```

Example investigation:

```sql
SELECT
    event_type,
    ip,
    country,
    city,
    timestamp
FROM enriched_events
ORDER BY id DESC
LIMIT 20;
```

Inspect one address:

```sql
SELECT
    event_type,
    ip,
    country,
    city,
    timestamp
FROM enriched_events
WHERE ip = '201.214.43.22'
ORDER BY id DESC;
```

---

## SSH session management

SSH Guardian can discover active SSH sessions and expose them through its management interfaces.

Example:

```text
Sessions SSH actives

PID: 151658
User: admin
IP: 82.80.219.126
TTY: pts/0
Status: LIVE / streamable
```

Inspect:

```text
/stream 151658
```

Terminate:

```text
/killsession 151658
```

Session termination is a privileged operation. Verify the target carefully before executing it.

---

## Running in production

SSH Guardian services can be managed through systemd.

Example:

```bash
systemctl status ssh-guardian@security
```

Restart a service:

```bash
systemctl restart ssh-guardian@security
```

View logs:

```bash
journalctl -u ssh-guardian@security -f
```

Check the complete stack:

```bash
systemctl --no-pager --full status \
  ssh-guardian@collector \
  ssh-guardian@geoip \
  ssh-guardian@security \
  ssh-guardian@firewall \
  ssh-guardian@storage \
  ssh-guardian@control \
  ssh-guardian@telegram \
  ssh-guardian@api \
  ssh-guardian@panel
```

### Avoid duplicate instances

Do not run a development instance and its systemd equivalent simultaneously.

For example, two Telegram processes using `getUpdates` can cause:

```text
409 Conflict
```

Check running Guardian processes:

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

There should normally be only **one instance of each production service**.

---

## Development mode

Start the development stack:

```bash
./scripts/start-dev.sh
```

Stop it:

```bash
./scripts/stop-dev.sh
```

Follow development logs:

```bash
./scripts/logs.sh
```

> Do not use the development stack simultaneously with the corresponding systemd services.

---

## Logs and diagnostics

### SSH Guardian processes

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

### Listening ports

```bash
ss -lntp | grep -E ':3000|:8080'
```

### Native SSH events

```bash
journalctl -u ssh --since -1h
```

Live:

```bash
journalctl -u ssh -f
```

### Security service

```bash
journalctl -u ssh-guardian@security -f
```

### Telegram service

```bash
journalctl -u ssh-guardian@telegram -f
```

### Firewall rules

```bash
iptables -L INPUT -n --line-numbers
```

---

## Testing

Run the complete test suite from the project root:

```bash
PYTHONPATH=. python3 -m pytest -q
```

Example:

```text
....................
20 passed in 0.17s
```

The test suite validates critical components such as event parsing, GeoIP processing, security decisions, database operations and firewall behavior.

---

## Troubleshooting

### Telegram returns `409 Conflict`

Example:

```text
409 Client Error: Conflict ... getUpdates
```

This usually means multiple processes are polling the same Telegram bot.

Check:

```bash
ps -ef | grep '[s]ervices.telegram.app.main'
```

Only one production Telegram instance should normally be running.

### API port already in use

Check:

```bash
ss -lntp | grep ':8080'
```

Then:

```bash
ps -ef | grep '[s]ervices.api.app.main'
```

Avoid running the API through both development scripts and systemd at the same time.

### Panel port already in use

```bash
ss -lntp | grep ':3000'
```

### Redis unavailable

```bash
redis-cli ping
```

Expected:

```text
PONG
```

### Inspect the complete SSH pipeline

```bash
journalctl -u ssh -f
```

In separate terminals:

```bash
journalctl -u ssh-guardian@collector -f
journalctl -u ssh-guardian@geoip -f
journalctl -u ssh-guardian@security -f
journalctl -u ssh-guardian@firewall -f
journalctl -u ssh-guardian@telegram -f
```

---

## Security recommendations

Before deploying SSH Guardian on an Internet-facing server:

1. Add your trusted administration IP addresses to `SG_WHITELIST`.
2. Test with `SG_FIREWALL_ENABLED=false`.
3. Verify GeoIP and security events.
4. Verify Telegram notifications.
5. Confirm that unban operations work correctly.
6. Keep the API bound to `127.0.0.1` unless external exposure is explicitly required.
7. Keep the Panel bound to `127.0.0.1` and access it through an SSH tunnel.
8. Protect `.env`, Telegram credentials and the Panel token.
9. Never run duplicate production/development consumers.
10. Only then enable real firewall enforcement.

---

## Secrets and Git

Never commit:

```text
.env
Telegram Bot tokens
Panel tokens
private SSH keys
database files containing operational data
runtime logs
```

A typical `.gitignore` should include:

```gitignore
.env

data/*.db
data/*.db-shm
data/*.db-wal

logs/*.log
run/*.pid

__pycache__/
*.pyc
.pytest_cache/

.venv/
venv/
```

The following file **should** remain versioned:

```text
.env.example
```

It documents the expected configuration without exposing real credentials.

---

## Uninstallation

Run:

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

Review the uninstall script before use if the machine contains data or firewall rules that must be preserved.

---

## Technology stack

<div align="center">

| Component | Technology |
|---|---|
| Runtime | Python |
| SSH server | OpenSSH |
| System events | journald |
| Event bus | Redis Streams |
| Database | SQLite |
| API | FastAPI |
| Dashboard | HTML / CSS / JavaScript |
| Notifications | Telegram Bot API |
| Firewall | Linux firewall / iptables |
| Service manager | systemd |
| Tests | pytest |

</div>

---

## Operational philosophy

SSH Guardian V2 follows four principles:

**Observable** — security activity should be visible and searchable.

**Modular** — collection, enrichment, detection, enforcement and presentation are separate services.

**Defensive** — firewall actions are generated from explicit security decisions and trusted addresses can be excluded through the whitelist.

**Private by default** — administrative HTTP services are intended to remain bound to localhost and be accessed securely when needed.

---

<div align="center">

### SSH Guardian V2

**From raw SSH logs to actionable security events.**

`COLLECT` · `ENRICH` · `DETECT` · `BLOCK` · `NOTIFY` · `INVESTIGATE`

<br>

Built for Linux servers running OpenSSH.

</div>

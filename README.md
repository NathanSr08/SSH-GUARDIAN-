# 🛡️ SSH Guardian V2

> Un mini Security Operations Center pour surveiller, analyser et protéger les accès SSH d'un serveur Linux.

SSH Guardian V2 surveille les connexions SSH en temps réel, géolocalise les adresses IP, détecte les tentatives suspectes, bloque automatiquement les attaquants et permet d'administrer le système depuis **Telegram** ou un **dashboard Web**.

---

# ✨ Fonctionnalités

- 🔎 Surveillance SSH en temps réel via `journald`
- 🌍 Géolocalisation des IP
- 🏙️ Ville / pays / code ISO / FAI
- 🚨 Détection des tentatives SSH échouées
- 🔢 Compteur de tentatives par IP
- 🚫 Bannissement automatique
- 🔥 Firewall Linux
- 🛡️ Whitelist
- 🌐 Blocage / déblocage de pays
- 📱 Notifications Telegram
- 🤖 Commandes administratives Telegram
- 🗄️ Historique SQLite
- ⚡ Redis Streams
- 🔌 API FastAPI
- 🖥️ Dashboard Web
- 💻 Gestion des sessions SSH
- 📡 Streaming des sessions enregistrées
- 🧪 Tests automatisés
- ⚙️ Installation automatique
- 🧹 Désinstallation automatique

---

# 🚀 Installation rapide

## 1️⃣ Récupérer le projet

```bash
git clone <URL_DU_DEPOT>
cd ssh-guardian-v2
```

Ou copie simplement le dossier sur ton serveur.

---

## 2️⃣ Lancer l'installation automatique

```bash
chmod +x install.sh
sudo ./install.sh
```

L'installateur configure automatiquement une grande partie de SSH Guardian :

- Python
- environnement Python
- dépendances
- Redis
- SQLite
- dossiers nécessaires
- configuration SSH Guardian
- recorder SSH
- configuration systemd
- API
- Panel
- génération du token Panel
- démarrage des services

---

# ⚙️ Configuration `.env`

SSH Guardian utilise un fichier :

```text
.env
```

à la racine du projet.

Ce fichier contient la configuration locale et les secrets.

⚠️ **Ne commit jamais `.env` dans Git.**

Un modèle est fourni :

```text
.env.example
```

Pour créer ta configuration :

```bash
cp .env.example .env
```

Puis :

```bash
nano .env
```

---

# 📝 Exemple de `.env`

Exemple simplifié :

```env
# =========================
# SSH Guardian
# =========================

SG_STATE_DIR=/etc/ssh-guardian
SG_SESSION_LOG_DIR=/var/log/ssh_recorder


# =========================
# Redis
# =========================

SG_REDIS_URL=redis://127.0.0.1:6379/0


# =========================
# Security
# =========================

SG_MAX_ATTEMPTS=3
SG_BAN_DURATION_SECONDS=86400

SG_WHITELIST=127.0.0.1,::1

SG_FIREWALL_ENABLED=false


# =========================
# Telegram
# =========================

SG_TELEGRAM_ENABLED=false
SG_TELEGRAM_TOKEN=
SG_TELEGRAM_CHAT_ID=


# =========================
# API
# =========================

SG_API_HOST=127.0.0.1
SG_API_PORT=8080


# =========================
# Panel
# =========================

SG_PANEL_HOST=127.0.0.1
SG_PANEL_PORT=3000
SG_PANEL_API_URL=http://127.0.0.1:8080

SG_PANEL_TOKEN=
```

---

# 🛡️ Configuration sécurité

## Nombre de tentatives

```env
SG_MAX_ATTEMPTS=3
```

Exemple :

```text
Tentative 1 → monitor
Tentative 2 → monitor
Tentative 3 → ban
```

---

## Durée du bannissement

```env
SG_BAN_DURATION_SECONDS=86400
```

`86400` secondes = :

```text
24 heures
```

---

# 🛡️ Whitelist

La whitelist contient les IP qui ne doivent jamais être bannies automatiquement.

Exemple :

```env
SG_WHITELIST=127.0.0.1,::1,TON_IP
```

Exemple réel :

```env
SG_WHITELIST=127.0.0.1,::1,82.80.219.126
```

⚠️ Avant d'activer le firewall, ajoute ton IP d'administration.

---

# 🔥 Firewall

## Mode test

Pendant l'installation ou les tests :

```env
SG_FIREWALL_ENABLED=false
```

SSH Guardian analysera les attaques mais n'ajoutera pas réellement les règles firewall.

Exemple :

```text
[FIREWALL]
status=dry_run
action=ban
ip=1.2.3.4
```

---

## Mode réel

Lorsque tout fonctionne :

```env
SG_FIREWALL_ENABLED=true
```

SSH Guardian appliquera réellement les bannissements.

⚠️ Configure d'abord correctement ta whitelist.

---

# 📱 Configuration Telegram

SSH Guardian peut envoyer les événements de sécurité directement sur Telegram.

Pour cela il faut :

```text
1. créer un bot
2. récupérer son token
3. envoyer un message au bot
4. récupérer ton Chat ID
5. mettre les deux dans .env
```

---

# 🤖 1. Créer un Bot Telegram

Dans Telegram, cherche :

```text
@BotFather
```

Ouvre la conversation.

Envoie :

```text
/newbot
```

BotFather te demandera d'abord un nom.

Exemple :

```text
SSH Guardian
```

Puis un username.

Le username doit normalement terminer par :

```text
bot
```

Exemple :

```text
ssh_guardian_myserver_bot
```

BotFather va ensuite te fournir un **token HTTP API**.

Exemple fictif :

```text
1234567890:AAEXEMPLE_TOKEN_NE_PAS_UTILISER
```

⚠️ Ce token est un secret.

Ne le publie jamais dans :

- GitHub
- GitLab
- README
- issue publique
- screenshot
- Discord public

---

# 🔑 2. Mettre le token Telegram dans `.env`

Exemple :

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=1234567890:AAEXEMPLE_TOKEN
```

Il manque maintenant le `CHAT_ID`.

---

# 💬 3. Envoyer un message au bot

Ouvre ton nouveau bot Telegram.

Clique :

```text
START
```

ou envoie :

```text
/start
```

C'est important : sans message reçu, `getUpdates` peut être vide.

---

# 🔎 4. Récupérer ton Telegram Chat ID

Place ton token dans une variable :

```bash
TOKEN="TON_TOKEN_TELEGRAM"
```

Puis :

```bash
curl "https://api.telegram.org/bot${TOKEN}/getUpdates"
```

Exemple de réponse :

```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {
          "id": 8714430026,
          "first_name": "Jean"
        },
        "chat": {
          "id": 8714430026,
          "first_name": "Jean",
          "type": "private"
        },
        "text": "/start"
      }
    }
  ]
}
```

La valeur importante est :

```json
"chat": {
    "id": 8714430026
}
```

Ton Chat ID est donc dans cet exemple :

```text
8714430026
```

---

# ⚡ Récupérer uniquement le Chat ID avec `jq`

Si `jq` est installé :

```bash
TOKEN="TON_TOKEN_TELEGRAM"

curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | jq '.result[-1].message.chat.id'
```

Résultat :

```text
8714430026
```

---

# ✅ 5. Configurer Telegram dans `.env`

Tu peux maintenant mettre :

```env
SG_TELEGRAM_ENABLED=true

SG_TELEGRAM_TOKEN=TON_TOKEN

SG_TELEGRAM_CHAT_ID=TON_CHAT_ID
```

Exemple fictif :

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=1234567890:AAEXEMPLE
SG_TELEGRAM_CHAT_ID=8714430026
```

---

# 🧪 Tester le Bot Telegram manuellement

Tu peux vérifier le token avec :

```bash
TOKEN="TON_TOKEN_TELEGRAM"

curl -s \
  "https://api.telegram.org/bot${TOKEN}/getMe" \
  | python3 -m json.tool
```

Résultat attendu :

```json
{
    "ok": true,
    "result": {
        "is_bot": true,
        "first_name": "SSH Guardian",
        "username": "ssh_guardian_myserver_bot"
    }
}
```

---

# 📤 Tester l'envoi d'un message

```bash
TOKEN="TON_TOKEN_TELEGRAM"
CHAT_ID="TON_CHAT_ID"

curl -s \
  -X POST \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  --data-urlencode "text=🛡️ SSH Guardian fonctionne !"
```

Tu dois recevoir :

```text
🛡️ SSH Guardian fonctionne !
```

sur Telegram.

---

# 🖥️ Configuration du Panel Web

Le dashboard écoute normalement sur :

```text
127.0.0.1:3000
```

Configuration :

```env
SG_PANEL_HOST=127.0.0.1
SG_PANEL_PORT=3000
```

L'API interne :

```env
SG_PANEL_API_URL=http://127.0.0.1:8080
```

---

# 🔑 Token administrateur du Panel

Le dashboard est protégé par un token.

Lors d'une installation avec :

```bash
sudo ./install.sh
```

SSH Guardian génère automatiquement un token sécurisé s'il n'en existe pas déjà.

Le token est créé avec Python grâce au module :

```python
secrets
```

et ressemble à :

```text
gZ7G0iA7oQDcX8Ypz8G2L-EpEXEMPLE
```

Il est enregistré dans :

```env
SG_PANEL_TOKEN=...
```

---

# 🔎 Retrouver le token Panel

Depuis la racine du projet :

```bash
grep '^SG_PANEL_TOKEN=' .env
```

Ou uniquement la valeur :

```bash
grep '^SG_PANEL_TOKEN=' .env | cut -d= -f2-
```

---

# 🔄 Générer un nouveau token Panel

```bash
NEW_TOKEN="$(
    python3 -c \
    'import secrets; print(secrets.token_urlsafe(32))'
)"

echo "$NEW_TOKEN"
```

Puis remplacer l'ancien :

```bash
sed -i '/^SG_PANEL_TOKEN=/d' .env

echo "SG_PANEL_TOKEN=$NEW_TOKEN" >> .env
```

Redémarre ensuite le Panel.

---

# 🔐 Accéder au Panel depuis Windows

Il est recommandé de ne **pas exposer directement le port 3000 sur Internet**.

Garde :

```env
SG_PANEL_HOST=127.0.0.1
```

Puis utilise un tunnel SSH.

Depuis PowerShell :

```powershell
ssh -i C:\chemin\vers\cle.pem -N -L 3000:127.0.0.1:3000 admin@TON_SERVEUR
```

Laisse cette fenêtre PowerShell ouverte.

Puis ouvre :

```text
http://127.0.0.1:3000
```

dans ton navigateur Windows.

Entre ensuite ton :

```text
SG_PANEL_TOKEN
```

---

# 🔌 API

L'API écoute normalement uniquement en local :

```env
SG_API_HOST=127.0.0.1
SG_API_PORT=8080
```

Tester :

```bash
curl http://127.0.0.1:8080/health
```

Top IP :

```bash
curl -s \
  http://127.0.0.1:8080/top \
  | python3 -m json.tool
```

Top pays :

```bash
curl -s \
  http://127.0.0.1:8080/topcountries \
  | python3 -m json.tool
```

---

# 🧩 Architecture

```text
                    OpenSSH
                       │
                       ▼
                   Collector
                       │
                  ssh.events
                       │
                       ▼
                     Redis
                       │
                       ▼
                     GeoIP
                       │
              ssh.events.enriched
                       │
         ┌─────────────┼───────────────┐
         │             │               │
         ▼             ▼               ▼
     Security       Storage         Telegram
         │             │
         │             ▼
         │           SQLite
         ▼             │
 security.actions      │
         │             │
         ▼             │
     Firewall          │
                       ▼
                      API
                       │
                       ▼
                     Panel
```

---

# 📂 Structure du projet

```text
ssh-guardian-v2/
│
├── .env
├── .env.example
├── README.md
├── requirements.txt
├── install.sh
├── uninstall.sh
│
├── data/
│   └── guardian.db
│
├── logs/
├── run/
├── scripts/
│
├── services/
│   ├── api/
│   ├── collector/
│   ├── control/
│   ├── database/
│   ├── firewall/
│   ├── geoip/
│   ├── panel/
│   ├── security/
│   ├── storage/
│   └── telegram/
│
├── shared/
│   ├── bus/
│   ├── config/
│   └── events/
│
└── tests/
```

---

# 🧪 Mode développement

Démarrer :

```bash
./scripts/start-dev.sh
```

Arrêter :

```bash
./scripts/stop-dev.sh
```

Voir les logs :

```bash
./scripts/logs.sh
```

---

# ⚠️ DEV et systemd

N'utilise pas simultanément :

```bash
./scripts/start-dev.sh
```

et :

```text
ssh-guardian@*.service
```

pour le même service.

Sinon deux processus peuvent essayer d'utiliser le même port.

Exemple :

```text
API dev → 127.0.0.1:8080

API systemd → essaie aussi 127.0.0.1:8080

→ Address already in use
```

---

# 📱 Principales commandes Telegram

## `/stats`

```text
/stats
```

Exemple :

```text
📊 Statistiques SSH Guardian

Connexions : 120
Échecs : 42
Succès : 8
IP uniques : 31
Bans : 12
```

---

## `/top`

```text
/top
```

Exemple :

```text
🏆 Top 20 IP attaquantes

1. 45.128.39.115 (Massamagrell, Spain) — 6
2. 82.80.219.126 (Maale Iron, Israel) — 4
3. 95.174.64.122 (Milan, Italy) — 3
4. 201.214.43.22 (Quillota, Chile) — 2
```

---

## `/topcountries`

```text
/topcountries
```

Exemple :

```text
🌍 Top pays attaquants

1. Spain — 8
2. Israel — 4
3. Italy — 3
4. Chile — 2
```

---

## `/search <IP>`

```text
/search 201.214.43.22
```

Permet d'afficher l'historique d'une adresse IP.

---

## `/bans`

```text
/bans
```

Affiche les IP bannies.

---

## `/unban <IP>`

```text
/unban 201.214.43.22
```

Exemple :

```text
🔓 IP débannie

IP : 201.214.43.22
Firewall : unbanned
```

---

## `/block <pays>`

Utilise le code ISO du pays :

```text
/block it
```

Exemple :

```text
🛡 Pays IT bloqué.

Toute nouvelle IP détectée dans ce pays
sera bannie automatiquement.
```

Autres exemples :

```text
/block ru
/block cn
/block az
```

---

## `/unblock <pays>`

```text
/unblock it
```

Exemple :

```text
🔓 Pays IT débloqué.

✅ IP précédemment bannies débloquées
```

---

## `/countries`

```text
/countries
```

Exemple :

```text
📜 Pays bloqués

• IT
• RU
• CN
```

---

## `/sessions`

```text
/sessions
```

Permet de consulter les sessions SSH actives.

Exemple :

```text
💻 Sessions SSH

Utilisateur : admin
IP : 82.80.219.126
PID : 151082
TTY : pts/1
```

---

## `/killsession`

```text
/killsession 151082
```

Termine la session SSH correspondante.

⚠️ Attention à ne pas tuer ta propre session.

---

## `/killallsessions`

```text
/killallsessions
```

Coupe les sessions SSH distantes gérées par le système.

---

## `/stream`

```text
/stream 151612
```

Permet de suivre une session SSH enregistrée lorsqu'elle est streamable.

Actions possibles :

```text
📡 suivre le terminal
⏹ arrêter le flux
💥 tuer la session
```

---

# 🚨 Exemple d'alerte Telegram

```text
🚨 Tentative SSH échouée

IP : 201.214.43.22
Localisation : Quillota, Chile
FAI : VTR BANDA ANCHA S.A.

Raison : connexion fermée avant authentification

Tentatives : 1/3
Avant bannissement : 2
```

Deuxième tentative :

```text
Tentatives : 2/3
Avant bannissement : 1
```

Puis bannissement au seuil configuré.

---

# 🌍 Gestion des pays en ligne de commande

Bloquer :

```bash
services/control/bin/country_blocker.sh block it
```

Débloquer :

```bash
services/control/bin/country_blocker.sh unblock it
```

Lister :

```bash
services/control/bin/country_blocker.sh list
```

---

# 🗄️ SQLite

La base principale :

```text
data/guardian.db
```

Ouvrir :

```bash
sqlite3 data/guardian.db
```

Derniers événements :

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

---

# ⚡ Redis

Tester Redis :

```bash
redis-cli ping
```

Résultat :

```text
PONG
```

Streams principaux :

```text
ssh.events
ssh.events.enriched
security.actions
firewall.events
```

Afficher leur taille :

```bash
redis-cli XLEN ssh.events
redis-cli XLEN ssh.events.enriched
redis-cli XLEN security.actions
redis-cli XLEN firewall.events
```

---

# 📋 Logs

Logs disponibles :

```text
logs/collector.log
logs/geoip.log
logs/security.log
logs/firewall.log
logs/storage.log
logs/control.log
logs/telegram.log
logs/api.log
logs/panel.log
```

Suivre Security :

```bash
tail -f logs/security.log
```

Suivre Telegram :

```bash
tail -f logs/telegram.log
```

Tous les logs :

```bash
./scripts/logs.sh
```

---

# 🩺 Diagnostic

## Voir les processus Guardian

```bash
ps -ef \
  | grep '[s]ervices\..*\.app\.main'
```

---

## Voir les ports API / Panel

```bash
ss -lntp \
  | grep -E ':3000|:8080'
```

---

## Voir les logs SSH système

```bash
journalctl -u ssh --since -1h
```

Temps réel :

```bash
journalctl -u ssh -f
```

---

## Voir le firewall

```bash
iptables -L INPUT -n --line-numbers
```

---

# 🧪 Tests

```bash
PYTHONPATH=. python3 -m pytest -q
```

Exemple :

```text
....................
20 passed in 0.17s
```

Les tests couvrent notamment :

```text
tests/test_database.py
tests/test_firewall.py
tests/test_geoip.py
tests/test_parser.py
tests/test_security.py
```

---

# 🧹 Désinstallation

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

---

# 🔐 `.gitignore`

Il est fortement recommandé d'avoir :

```gitignore
.env

data/*.db
data/*.db-shm
data/*.db-wal

logs/*.log

run/*.pid

__pycache__/
.pytest_cache/

*.pyc
```

Le fichier :

```text
.env.example
```

peut en revanche être publié.

---

# 🛠️ Stack

| Technologie | Rôle |
|---|---|
| 🐍 Python | Backend |
| ⚡ Redis | Bus temps réel |
| 🗄️ SQLite | Historique |
| 🌐 FastAPI | API |
| 🖥️ HTML / CSS / JS | Dashboard |
| 🔥 iptables / ipset | Firewall |
| 🔐 OpenSSH | SSH |
| 📜 journald | Logs système |
| 📱 Telegram Bot API | Notifications |
| 🧪 pytest | Tests |
| 🐧 systemd | Production |

---

# 🎯 Résumé

```text
Connexion SSH
      │
      ▼
   Collector
      │
      ▼
    GeoIP
      │
      ▼
   Security
      │
      ├────► Monitor
      │
      └────► Ban
               │
               ▼
            Firewall

En parallèle :

événements
    │
    ├────► SQLite
    ├────► Telegram
    ├────► API
    └────► Dashboard
```

---

# ❤️ SSH Guardian V2

**Un mini SOC dédié à ton serveur SSH.**

🛡️ Surveille  
🌍 Géolocalise  
🚨 Détecte  
🔥 Bloque  
📱 Notifie  
📊 Analyse  
💻 Administre

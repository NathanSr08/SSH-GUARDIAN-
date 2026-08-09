# 🛡️ SSH Guardian V2

> Surveillance SSH en temps réel, géolocalisation, bannissement automatique, alertes Telegram, API et dashboard Web.

SSH Guardian V2 est un outil de sécurité pour serveurs Linux qui surveille les connexions SSH, détecte les tentatives suspectes, géolocalise les IP, bloque automatiquement les attaquants et permet d'administrer le serveur depuis Telegram ou un panel Web.

---

## ✨ Fonctionnalités

- 🔎 Surveillance SSH en temps réel via `journalctl`
- 🌍 Géolocalisation IP : pays, ville, code pays et FAI
- 🚨 Détection des tentatives SSH échouées
- 🔢 Compteur de tentatives par IP
- 🚫 Bannissement automatique après plusieurs échecs
- 🧱 Blocage réel via le firewall Linux
- 🛡️ Whitelist des IP de confiance
- 🌐 Blocage / déblocage de pays
- 📱 Alertes Telegram
- 🤖 Administration via commandes Telegram
- 🗄️ Historique SQLite
- ⚡ Communication temps réel via Redis Streams
- 🔌 API HTTP
- 🖥️ Dashboard Web
- 💻 Gestion des sessions SSH
- 📡 Suivi des sessions
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

Ou copie simplement le projet sur ton serveur.

---

## 2️⃣ Lancer l'installation

```bash
chmod +x install.sh
sudo ./install.sh
```

L'installateur configure automatiquement les composants nécessaires à SSH Guardian.

Il s'occupe notamment de :

- Python
- dépendances Python
- Redis
- SQLite
- configuration SSH Guardian
- répertoires de données
- logs
- configuration systemd
- environnement du projet
- génération du token Panel
- démarrage des services

---

# 🔑 Token du Panel

Le dashboard SSH Guardian est protégé par un **token administrateur**.

Lors de l'installation, `install.sh` génère automatiquement un token aléatoire sécurisé.

Exemple :

```text
SG_PANEL_TOKEN=0DcQYvQ2Vd2Qj7zYoO3n8QxEXEMPLE
```

Le token est enregistré dans :

```text
.env
```

À la fin de l'installation, l'installateur doit afficher quelque chose comme :

```text
============================================================
          SSH GUARDIAN V2 INSTALLÉ
============================================================

🌐 Panel :
http://127.0.0.1:3000

🔑 Token Panel :

0DcQYvQ2Vd2Qj7zYoO3n8QxEXEMPLE

============================================================
```

Au premier accès au dashboard, entre ce token dans le champ :

```text
Token administrateur
```

## 🔍 Retrouver son token

Depuis la racine de SSH Guardian :

```bash
grep '^SG_PANEL_TOKEN=' .env
```

Pour afficher uniquement le token :

```bash
grep '^SG_PANEL_TOKEN=' .env | cut -d= -f2-
```

> 🔐 Ne publie jamais ton token Panel dans GitHub, un README public, une issue ou une capture d'écran.

---

# 🧪 Mode développement

Démarrer SSH Guardian :

```bash
./scripts/start-dev.sh
```

Arrêter SSH Guardian :

```bash
./scripts/stop-dev.sh
```

Afficher les logs :

```bash
./scripts/logs.sh
```

Les services principaux sont :

```text
collector
geoip
security
firewall
storage
control
telegram
api
panel
```

> ⚠️ N'utilise pas simultanément `start-dev.sh` et les mêmes services lancés avec systemd.

---

# 🧩 Architecture

```text
                    ┌──────────────┐
                    │   OpenSSH    │
                    └──────┬───────┘
                           │
                       journald
                           │
                           ▼
                    ┌──────────────┐
                    │  Collector   │
                    └──────┬───────┘
                           │
                       ssh.events
                           │
                           ▼
                        Redis
                           │
                           ▼
                    ┌──────────────┐
                    │    GeoIP     │
                    └──────┬───────┘
                           │
                 ssh.events.enriched
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
          Security      Storage      Telegram
              │            │
              ▼            ▼
      security.actions   SQLite
              │            │
              ▼            │
          Firewall         │
              │            │
              ▼            ▼
           Linux          API
        Firewall           │
                           ▼
                         Panel
```

---

# 📂 Structure du projet

```text
ssh-guardian-v2/
│
├── install.sh
├── uninstall.sh
├── requirements.txt
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

# 🔄 Exemple d'une tentative SSH

Une IP contacte le serveur :

```text
Connection from 201.214.43.22
```

Le Collector détecte :

```text
ssh.connection.opened
```

GeoIP enrichit l'événement :

```text
IP        : 201.214.43.22
Pays      : Chile
Code pays : CL
Ville     : Quillota
FAI       : VTR BANDA ANCHA S.A.
```

Si la connexion est fermée avant authentification :

```text
ssh.connection.closed
```

SSH Guardian peut envoyer sur Telegram :

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

Au seuil configuré :

```text
Tentatives : 3/3
```

SSH Guardian demande le bannissement de l'IP.

---

# 📱 Telegram

SSH Guardian peut envoyer automatiquement des alertes Telegram.

Exemple :

```text
🚨 Tentative SSH échouée

Utilisateur : admin
IP : 193.9.114.210
Localisation : Zaventem, Belgium
FAI : M247 Europe SRL

Tentatives : 1/3
Avant bannissement : 2
```

Lorsqu'une IP est bannie :

```text
🛡 IP bannie

IP : 95.174.64.122
Raison : blocked_country
Durée : 24 h
Firewall : banned
```

---

# 📊 Commande `/stats`

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

# 🏆 Commande `/top`

Affiche les IP attaquantes.

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

# 🌍 Commande `/topcountries`

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
5. Azerbaijan — 2
```

---

# 🔎 Commande `/search`

Recherche une IP :

```text
/search 201.214.43.22
```

Exemple :

```text
🔎 Informations IP

IP : 201.214.43.22
Pays : Chile
Ville : Quillota
FAI : VTR BANDA ANCHA S.A.

Événements :
ssh.connection.opened
ssh.connection.closed
ssh.connection.opened
ssh.connection.closed
```

---

# 🚫 Voir les bans

```text
/bans
```

Exemple :

```text
🚫 IP bannies

45.128.39.115
95.174.64.122
201.214.43.22
```

---

# 🔓 Débannir une IP

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

# 🌐 Bloquer un pays

Utilise son code ISO.

Exemple pour l'Italie :

```text
/block it
```

Résultat :

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

# 🔓 Débloquer un pays

```text
/unblock it
```

Exemple :

```text
🔓 Pays IT débloqué.

✅ 3 IP(s) débannie(s)
```

Les IP précédemment bannies à cause de `blocked_country` peuvent ainsi être débannies lors du déblocage du pays.

---

# 📜 Voir les pays bloqués

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

# 💻 Sessions SSH

Afficher les sessions :

```text
/sessions
```

Exemple :

```text
💻 Sessions SSH

Utilisateur : admin
IP : 82.80.219.126
PID : 151082
TTY : pts/1
```

---

# 💥 Tuer une session

```text
/killsession 151082
```

> ⚠️ Attention : cela termine réellement la session SSH ciblée.

---

# ⚡ Tuer les sessions

```text
/killallsessions
```

À utiliser avec prudence afin de ne pas couper ta propre session d'administration.

---

# 📡 Stream d'une session

```text
/stream 151612
```

Permet de suivre une session enregistrée lorsque cette fonctionnalité est disponible pour la session concernée.

---

# 🌍 Gestion des pays en CLI

Le gestionnaire se trouve dans :

```text
services/control/bin/country_blocker.sh
```

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

# 🔥 Firewall

SSH Guardian peut fonctionner en simulation ou en mode réel.

## 🧪 DRY-RUN

Dans `.env` :

```env
SG_FIREWALL_ENABLED=false
```

Les actions sont calculées mais aucune règle firewall réelle n'est ajoutée.

Exemple :

```text
status=dry_run
action=ban
ip=1.2.3.4
```

---

## 🔥 Firewall actif

```env
SG_FIREWALL_ENABLED=true
```

Les bannissements sont réellement appliqués.

> ⚠️ Avant d'activer cette option, configure correctement ta whitelist.

---

# 🛡️ Whitelist

Ajoute les IP qui ne doivent jamais être bannies.

Exemple :

```env
SG_WHITELIST=127.0.0.1,::1,TON_IP
```

Une IP whitelistée doit être ignorée par les règles automatiques de bannissement.

---

# 🗄️ SQLite

La base principale se trouve dans :

```text
data/guardian.db
```

Ouvrir la base :

```bash
sqlite3 data/guardian.db
```

Afficher les derniers événements :

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

Quitter :

```text
.quit
```

---

# ⚡ Redis Streams

Redis permet aux services de communiquer en temps réel.

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
```

```bash
redis-cli XLEN ssh.events.enriched
```

```bash
redis-cli XLEN security.actions
```

```bash
redis-cli XLEN firewall.events
```

---

# 🌐 API HTTP

L'API écoute normalement uniquement en local :

```text
127.0.0.1:8080
```

Tester :

```bash
curl http://127.0.0.1:8080/health
```

Top IP :

```bash
curl -s http://127.0.0.1:8080/top | python3 -m json.tool
```

Top pays :

```bash
curl -s http://127.0.0.1:8080/topcountries | python3 -m json.tool
```

Exemple :

```json
[
    {
        "ip": "201.214.43.22",
        "country": "Chile",
        "country_code": "CL",
        "city": "Quillota",
        "isp": "VTR BANDA ANCHA S.A.",
        "attempts": 2
    }
]
```

---

# 🖥️ Dashboard Web

Le panel écoute normalement sur :

```text
127.0.0.1:3000
```

Il permet notamment de voir :

- 📊 statistiques globales
- ⚙️ état des services
- 🏆 Top IP
- 🌍 Top pays
- 🚫 bans actifs
- 📜 pays bloqués
- 📋 événements récents
- 💻 sessions SSH
- 🔎 informations sur les IP

---

# 🔐 Accéder au Panel depuis Windows

Il est recommandé de garder le panel sur `127.0.0.1`.

Depuis PowerShell, crée un tunnel SSH :

```powershell
ssh -i C:\chemin\vers\cle.pem -N -L 3000:127.0.0.1:3000 admin@TON_SERVEUR
```

Puis ouvre dans ton navigateur :

```text
http://127.0.0.1:3000
```

Entre ensuite le token administrateur généré pendant l'installation.

---

# 🔑 Retrouver le token Panel

Sur le serveur :

```bash
cd /chemin/vers/ssh-guardian-v2
grep '^SG_PANEL_TOKEN=' .env | cut -d= -f2-
```

---

# 🔄 Changer le token Panel

Générer un nouveau token :

```bash
NEW_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

sed -i '/^SG_PANEL_TOKEN=/d' .env
echo "SG_PANEL_TOKEN=$NEW_TOKEN" >> .env

echo "Nouveau token : $NEW_TOKEN"
```

Redémarre ensuite SSH Guardian.

En mode développement :

```bash
./scripts/stop-dev.sh
./scripts/start-dev.sh
```

---

# 📋 Logs

Tous les logs applicatifs sont disponibles dans :

```text
logs/
```

Exemples :

```text
collector.log
geoip.log
security.log
firewall.log
storage.log
control.log
telegram.log
api.log
panel.log
```

Suivre Security :

```bash
tail -f logs/security.log
```

Suivre Telegram :

```bash
tail -f logs/telegram.log
```

Tout afficher :

```bash
./scripts/logs.sh
```

---

# 🩺 Diagnostic rapide

## Redis

```bash
redis-cli ping
```

Résultat attendu :

```text
PONG
```

---

## API

```bash
curl http://127.0.0.1:8080/health
```

---

## Ports

```bash
ss -lntp | grep -E ':3000|:8080'
```

Exemple :

```text
127.0.0.1:3000
127.0.0.1:8080
```

---

## Processus

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

---

## Firewall

```bash
iptables -L INPUT -n --line-numbers
```

---

## Logs SSH système

```bash
journalctl -u ssh --since -1h
```

En temps réel :

```bash
journalctl -u ssh -f
```

---

# 🧪 Tests

Depuis la racine du projet :

```bash
PYTHONPATH=. python3 -m pytest -q
```

Exemple de résultat :

```text
....................
20 passed in 0.17s
```

Les tests couvrent notamment :

```text
test_database.py
test_firewall.py
test_geoip.py
test_parser.py
test_security.py
```

---

# ⚙️ Systemd

Si SSH Guardian est installé en tant que services systemd :

```bash
systemctl status ssh-guardian@collector
systemctl status ssh-guardian@geoip
systemctl status ssh-guardian@security
systemctl status ssh-guardian@firewall
systemctl status ssh-guardian@storage
systemctl status ssh-guardian@control
systemctl status ssh-guardian@telegram
systemctl status ssh-guardian@api
systemctl status ssh-guardian@panel
```

Redémarrer un service :

```bash
systemctl restart ssh-guardian@security
```

---

# ⚠️ Mode DEV ou systemd

Utilise **un seul mode à la fois**.

### Mode DEV

```bash
./scripts/start-dev.sh
```

### Mode production

```bash
systemctl start ssh-guardian@collector
```

Ne lance pas une deuxième instance de l'API sur le même port.

Sinon tu peux obtenir :

```text
Address already in use
```

---

# 🧹 Désinstallation

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

Le script retire les composants SSH Guardian installés sur la machine.

---

# 🔐 Sécurité

Quelques recommandations importantes :

- 🛡️ Ajoute ton IP d'administration à la whitelist.
- 🧪 Teste d'abord le firewall en mode `false`.
- 🔑 Ne publie jamais `SG_PANEL_TOKEN`.
- 🤖 Ne publie jamais le token Telegram.
- 📁 N'ajoute pas `.env` dans Git.
- 🔒 Garde idéalement API et Panel sur `127.0.0.1`.
- 🔐 Utilise un tunnel SSH pour accéder au dashboard.
- 💾 Sauvegarde `data/guardian.db` avant une grosse modification.
- ⚠️ Vérifie toujours que tu disposes d'un second accès au serveur avant de tester des règles firewall.

Exemple `.gitignore` :

```gitignore
.env
data/*.db
data/*.db-shm
data/*.db-wal
logs/*.log
run/*.pid
__pycache__/
.pytest_cache/
```

---

# 🛠️ Stack technique

| Technologie | Utilisation |
|---|---|
| 🐍 Python | Services backend |
| ⚡ Redis | Bus d'événements |
| 🗄️ SQLite | Persistance |
| 🌐 FastAPI | API / Panel backend |
| 🖥️ HTML/CSS/JS | Dashboard |
| 🔥 iptables / ipset | Firewall |
| 🐧 systemd | Services |
| 🔐 OpenSSH | Source des événements |
| 📜 journald | Lecture des logs |
| 📱 Telegram | Notifications et administration |
| 🧪 pytest | Tests |

---

# 🎯 Fonctionnement résumé

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
      ├──── OK ────► Monitoring
      │
      └──── BAN
              │
              ▼
           Firewall
              │
              ▼
          IP bloquée

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

**Un mini Security Operations Center dédié à la protection et à la supervision de ton serveur SSH.**

🛡️ Surveille  
🌍 Géolocalise  
🚨 Détecte  
🔥 Bloque  
📱 Notifie  
📊 Analyse  
💻 Administre

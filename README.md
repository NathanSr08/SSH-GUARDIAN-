<div align="center">

# 🛡️ SSH Guardian V2

### Protection SSH en temps réel pour serveurs Linux

Surveillance · GeoIP · Firewall · Telegram · API · Dashboard

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Debian%20%7C%20Ubuntu-FCC624?logo=linux&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-Services-000000?logo=linux&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

</div>

---

## 👋 À quoi sert SSH Guardian ?

SSH Guardian V2 transforme les logs OpenSSH d'un serveur Linux en événements de sécurité exploitables.

Il peut notamment :

- détecter les nouvelles connexions SSH ;
- détecter les connexions interrompues ou échouées ;
- compter les tentatives par IP ;
- géolocaliser les adresses IP ;
- bannir automatiquement une IP ;
- bloquer un pays entier ;
- envoyer des alertes Telegram ;
- afficher les sessions SSH actives ;
- terminer une session à distance ;
- conserver l'historique dans SQLite ;
- afficher les données dans un dashboard Web.

Le projet est composé de plusieurs services indépendants plutôt que d'un gros script unique. Cette architecture est déjà au cœur de la version actuelle. :contentReference[oaicite:1]{index=1}

---

## ⚡ Installation rapide

Le parcours recommandé est simple :

```text
1. Créer le bot Telegram
2. Récupérer TOKEN + CHAT_ID
3. Cloner le projet
4. Lancer install.sh
5. Compléter .env
6. Redémarrer les services
7. Tester Telegram
8. Ouvrir le dashboard
```

### 1. Préparer Telegram

Avant d'installer SSH Guardian, crée ton bot.

Dans Telegram, ouvre :

```text
@BotFather
```

Envoie :

```text
/newbot
```

Choisis un nom, par exemple :

```text
SSH Guardian
```

Puis un username unique, par exemple :

```text
my_ssh_guardian_bot
```

BotFather te donnera un token :

```text
1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxx
```

🔐 **Garde ce token privé.**

---

### 2. Récupérer ton Chat ID

Ouvre ton nouveau bot et envoie :

```text
/start
```

Sur ton serveur :

```bash
TOKEN="TON_TOKEN_TELEGRAM"

curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | python3 -m json.tool
```

Cherche :

```json
"chat": {
    "id": 123456789
}
```

Ton Chat ID est donc :

```text
123456789
```

Avec `jq` :

```bash
curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | jq '.result[-1].message.chat.id'
```

Tu dois maintenant avoir :

```text
TOKEN Telegram
CHAT ID Telegram
```

---

### 3. Cloner le projet

```bash
git clone <URL_DU_DEPOT>
cd SSH-GUARDIAN-
```

---

### 4. Lancer l'installation

```bash
chmod +x install.sh
sudo ./install.sh
```

L'installateur prépare automatiquement l'environnement :

```text
✓ Python
✓ dépendances
✓ Redis
✓ SQLite
✓ dossiers runtime
✓ configuration OpenSSH
✓ SSH recorder
✓ services systemd
✓ fichier .env
✓ token du Panel
```

Le fichier `.env` est généré automatiquement par `install.sh`.

Tu n'as donc **pas besoin de créer `.env` manuellement**.

---

### 5. Compléter `.env`

Après l'installation :

```bash
nano .env
```

Les valeurs importantes à vérifier sont principalement celles-ci :

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=TON_TOKEN
SG_TELEGRAM_CHAT_ID=TON_CHAT_ID

SG_MAX_ATTEMPTS=3
SG_BAN_DURATION_SECONDS=86400

SG_WHITELIST=127.0.0.1,::1,TON_IP

SG_FIREWALL_ENABLED=false
```

#### Telegram

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=TON_TOKEN
SG_TELEGRAM_CHAT_ID=TON_CHAT_ID
```

#### Whitelist

Ajoute l'IP depuis laquelle tu administres le serveur :

```env
SG_WHITELIST=127.0.0.1,::1,TON_IP
```

⚠️ Fais cette étape **avant d'activer le firewall réel**.

#### Firewall

Pour les premiers tests :

```env
SG_FIREWALL_ENABLED=false
```

Lorsque tout est validé :

```env
SG_FIREWALL_ENABLED=true
```

#### Nombre de tentatives

```env
SG_MAX_ATTEMPTS=3
```

Ce qui donne :

```text
1/3 → surveillance
2/3 → surveillance
3/3 → bannissement
```

---

### 6. Redémarrer SSH Guardian

Après modification du `.env` :

```bash
sudo systemctl restart \
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

---

### 7. Vérifier l'installation

Redis :

```bash
redis-cli ping
```

Résultat attendu :

```text
PONG
```

API :

```bash
curl -s http://127.0.0.1:8080/health \
  | python3 -m json.tool
```

Services :

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

---

## 📱 Utiliser le bot Telegram

Une fois installé, commence simplement par :

```text
/stats
```

Puis :

```text
/top
```

Si le bot répond, la communication Telegram fonctionne.

### Commandes principales

| Commande | Action |
|---|---|
| `/stats` | Statistiques générales |
| `/top` | IP les plus actives |
| `/topcountries` | Pays les plus actifs |
| `/search <IP>` | Rechercher une IP |
| `/bans` | Voir les bans |
| `/unban <IP>` | Débannir une IP |
| `/countries` | Voir les pays bloqués |
| `/block <CC>` | Bloquer un pays |
| `/unblock <CC>` | Débloquer un pays |
| `/sessions` | Voir les sessions SSH |
| `/active` | Voir les sessions actives |
| `/stream <ID>` | Suivre une session |
| `/killsession <PID>` | Terminer une session |
| `/killallsessions` | Terminer les sessions distantes |

Ces commandes correspondent aux fonctionnalités déjà exposées par l'interface Telegram actuelle. :contentReference[oaicite:2]{index=2}

---

### 📊 Statistiques

```text
/stats
```

Exemple :

```text
📊 Statistiques SSH Guardian

Connexions : 142
Échecs : 37
Succès : 8
IP uniques : 29
Bans : 11
```

---

### 🏆 Top IP

```text
/top
```

Exemple :

```text
🏆 Top IP attaquantes

1. 45.128.39.115 — 6
2. 82.80.219.126 — 4
3. 95.174.64.122 — 3
```

---

### 🌍 Top pays

```text
/topcountries
```

Exemple :

```text
🌍 Top pays attaquants

1. Spain — 8
2. Israel — 4
3. Italy — 3
```

---

### 🔎 Rechercher une IP

```text
/search 203.0.113.10
```

Permet de retrouver les informations connues et les événements associés à cette adresse.

---

### 🚫 Gérer les bans

Afficher les bans :

```text
/bans
```

Débannir une IP :

```text
/unban 203.0.113.10
```

---

### 🌐 Bloquer un pays

Les pays utilisent leur code ISO.

Exemples :

```text
FR → France
IT → Italie
IL → Israël
ES → Espagne
GB → Royaume-Uni
US → États-Unis
```

Bloquer :

```text
/block fr
```

Débloquer :

```text
/unblock fr
```

Afficher la liste :

```text
/countries
```

---

### 💻 Sessions SSH

Afficher les sessions :

```text
/sessions
```

ou :

```text
/active
```

Exemple :

```text
Sessions SSH actives

PID : 151658
Utilisateur : admin
IP : 203.0.113.20
TTY : pts/0
LIVE / streamable
```

Suivre une session :

```text
/stream 151658
```

Terminer cette session :

```text
/killsession 151658
```

⚠️ Vérifie toujours le PID avant de terminer une session.

---

## 🖥️ Dashboard Web

Le Panel permet de consulter depuis une interface Web :

```text
✓ état des services
✓ connexions
✓ échecs
✓ succès
✓ IP uniques
✓ bans
✓ Top IP
✓ Top pays
✓ pays bloqués
✓ événements récents
✓ sessions SSH
```

Le dashboard fait partie des fonctionnalités déjà présentes dans le projet actuel. :contentReference[oaicite:3]{index=3}

### Token du Panel

Le token est généré automatiquement pendant l'installation.

Pour l'afficher :

```bash
grep '^SG_PANEL_TOKEN=' .env \
  | cut -d= -f2-
```

🔐 Garde ce token privé.

---

### Accès sécurisé au Panel

Il est recommandé de passer par un tunnel SSH plutôt que d'exposer directement le Panel sur Internet.

Depuis ton ordinateur :

```bash
ssh -i "CHEMIN_VERS_TA_CLE.pem" \
  -N \
  -L 3000:127.0.0.1:3000 \
  UTILISATEUR@SERVEUR
```

Sous PowerShell :

```powershell
ssh -i "CHEMIN_VERS_TA_CLE.pem" -N -L 3000:127.0.0.1:3000 UTILISATEUR@SERVEUR
```

Puis ouvre :

```text
http://127.0.0.1:3000
```

---

## 🧠 Comment ça fonctionne ?

Quand quelqu'un contacte SSH :

```text
Connexion SSH
     │
     ▼
 Collector
     │
     ▼
   Redis
     │
     ▼
   GeoIP
     │
     ▼
 Security
     │
     ├── IP whitelistée ──────► ignorée
     │
     ├── tentative normale ───► surveillée
     │
     ├── seuil atteint ───────► ban
     │
     └── pays bloqué ─────────► ban
                                  │
                                  ▼
                              Firewall
```

En parallèle :

```text
événements
   │
   ├──► SQLite
   ├──► Telegram
   ├──► API
   └──► Dashboard
```

---

## 🧩 Services

SSH Guardian est composé de plusieurs services :

| Service | Rôle |
|---|---|
| `collector` | Lit les événements OpenSSH |
| `geoip` | Géolocalise les IP |
| `security` | Décide quoi surveiller ou bloquer |
| `firewall` | Applique les bans |
| `storage` | Enregistre l'historique |
| `control` | Exécute les commandes |
| `telegram` | Bot + notifications |
| `api` | API HTTP |
| `panel` | Interface Web |

---

## 📂 Structure du projet

```text
SSH-GUARDIAN-/
│
├── services/
│   ├── collector/
│   ├── geoip/
│   ├── security/
│   ├── firewall/
│   ├── storage/
│   ├── control/
│   ├── telegram/
│   ├── api/
│   └── panel/
│
├── shared/
├── scripts/
├── tests/
├── data/
├── logs/
├── run/
│
├── install.sh
├── uninstall.sh
├── requirements.txt
└── README.md
```

---

## 🔌 API

L'API écoute par défaut en local.

Health check :

```bash
curl -s http://127.0.0.1:8080/health \
  | python3 -m json.tool
```

Top IP :

```bash
curl -s http://127.0.0.1:8080/top \
  | python3 -m json.tool
```

Top pays :

```bash
curl -s http://127.0.0.1:8080/topcountries \
  | python3 -m json.tool
```

---

## 🗄️ Données

### SQLite

Base principale :

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

### Redis

Tester :

```bash
redis-cli ping
```

Streams principaux :

```text
ssh.events
ssh.events.enriched
security.actions
firewall.events
control.commands
```

Voir les derniers événements :

```bash
redis-cli XREVRANGE security.actions + - COUNT 10
```

---

## 📋 Logs

Security :

```bash
journalctl -u ssh-guardian@security -f
```

Firewall :

```bash
journalctl -u ssh-guardian@firewall -f
```

Telegram :

```bash
journalctl -u ssh-guardian@telegram -f
```

API :

```bash
journalctl -u ssh-guardian@api -f
```

Panel :

```bash
journalctl -u ssh-guardian@panel -f
```

Logs OpenSSH :

```bash
journalctl -u ssh -f
```

Si le service s'appelle `sshd` :

```bash
journalctl -u sshd -f
```

---

## 🧪 Tests

Depuis la racine du projet :

```bash
PYTHONPATH=. python3 -m pytest -q
```

Mode détaillé :

```bash
PYTHONPATH=. python3 -m pytest -v
```

La suite couvre notamment :

```text
✓ parser SSH
✓ database
✓ firewall
✓ GeoIP
✓ Security Engine
✓ compteurs
✓ bannissement
✓ whitelist
```

La documentation détaillée des tests peut être placée dans :

```text
tests/README.md
```

---

## 🛠️ Développement

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

> ⚠️ Ne lance pas simultanément le mode DEV et les mêmes services via systemd.

---

## 🩺 Dépannage rapide

### Telegram affiche `409 Conflict`

Vérifie qu'un seul bot tourne :

```bash
ps -ef | grep '[s]ervices.telegram.app.main'
```

Il ne doit normalement y avoir qu'une seule instance Telegram.

---

### API indisponible

```bash
ss -lntp | grep ':8080'
```

Puis :

```bash
systemctl status ssh-guardian@api
```

---

### Panel indisponible

```bash
ss -lntp | grep ':3000'
```

Puis :

```bash
systemctl status ssh-guardian@panel
```

---

### Redis indisponible

```bash
redis-cli ping
```

Résultat attendu :

```text
PONG
```

---

### Voir tous les processus

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

---

## 🔐 Bonnes pratiques

Avant d'activer le firewall réel :

```text
✓ garder une session SSH ouverte
✓ mettre son IP en whitelist
✓ tester Telegram
✓ tester le Panel
✓ vérifier les événements GeoIP
✓ tester /unban
✓ tester /block et /unblock
✓ vérifier qu'il n'existe pas de doubles processus
```

Puis seulement :

```env
SG_FIREWALL_ENABLED=true
```

Ne commit jamais :

```text
.env
tokens Telegram
token Panel
clés SSH privées
logs sensibles
```

---

## 🗑️ Désinstallation

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

---

<div align="center">

### 🛡️ SSH Guardian V2

**Un mini SOC dédié à la surveillance et à la protection de ton serveur SSH.**

`COLLECT` · `ENRICH` · `DETECT` · `BLOCK` · `NOTIFY`

</div>

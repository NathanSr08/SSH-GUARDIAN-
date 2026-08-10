<div align="center">

# 🛡️ SSH Guardian V2

### Protection SSH en temps réel pour serveurs Linux

Surveillance · GeoIP · Firewall · Telegram · MFA · API · Dashboard

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Debian%20%7C%20Ubuntu-FCC624?logo=linux&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![MFA](https://img.shields.io/badge/MFA-Telegram%20Approval-8A2BE2?logo=telegram&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-Services-000000?logo=linux&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

</div>

---

## 👋 À quoi sert SSH Guardian ?

SSH Guardian V2 transforme les logs OpenSSH d'un serveur Linux en événements de sécurité exploitables.

Il peut notamment :

- détecter les nouvelles connexions SSH ;
- détecter les connexions interrompues ou échouées ;
- détecter les utilisateurs SSH invalides ;
- compter les tentatives par IP ;
- géolocaliser les adresses IP ;
- identifier le pays, la ville et le FAI ;
- bannir automatiquement une IP ;
- bloquer un pays entier ;
- envoyer des alertes Telegram ;
- afficher les sessions SSH actives ;
- suivre un terminal SSH en direct ;
- terminer une session à distance ;
- conserver l'historique dans SQLite ;
- afficher les données dans un dashboard Web ;
- protéger SSH avec une deuxième validation MFA ;
- envoyer une demande d'autorisation SSH sur Telegram ;
- autoriser ou refuser une connexion depuis Telegram ;
- autoriser temporairement une IP sans nouvelle validation MFA ;
- modifier le timeout MFA à chaud ;
- activer ou désactiver le MFA sans reconfigurer OpenSSH ;
- gérer le MFA depuis le Panel Web ;
- gérer les demandes MFA depuis l'API.

Le projet est composé de plusieurs services indépendants plutôt que d'un gros script unique.

Chaque composant possède un rôle précis et communique avec les autres services via Redis Streams.

---

## ⚡ Installation rapide

Le parcours recommandé est simple :

```text
1. Créer le bot Telegram
2. Récupérer TOKEN + CHAT_ID
3. Vérifier que la clé SSH fonctionne
4. Cloner le projet
5. Lancer install.sh
6. Compléter .env
7. Redémarrer les services
8. Tester Telegram
9. Tester le MFA
10. Ouvrir le dashboard
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

### 3. Vérifier ta clé SSH

Le MFA repose sur :

```text
clé publique SSH
        +
validation PAM / Telegram
```

Avant toute installation MFA, assure-toi donc que ta clé SSH fonctionne correctement.

Depuis ton ordinateur :

```bash
ssh -i "CLE.pem" UTILISATEUR@SERVEUR
```

⚠️ Garde toujours une deuxième session SSH ouverte pendant les premiers tests MFA.

---

### 4. Cloner le projet

```bash
git clone <URL_DU_DEPOT>
cd SSH-GUARDIAN-
```

---

### 5. Lancer l'installation

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
✓ service MFA
✓ bridge PAM MFA
✓ wrapper ssh-guardian-mfa
✓ configuration OpenSSH MFA
✓ runtime MFA Redis
✓ streams MFA
✓ sauvegarde PAM
✓ sauvegarde OpenSSH
✓ validation sshd -t
✓ rollback automatique si la configuration MFA/SSH est invalide
```

Le fichier `.env` est généré automatiquement par `install.sh`.

Tu n'as donc **pas besoin de créer `.env` manuellement**.

---

### 6. Compléter `.env`

Après l'installation :

```bash
nano .env
```

Ou avec ton éditeur préféré.

Les valeurs importantes à vérifier sont principalement celles-ci :

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=TON_TOKEN
SG_TELEGRAM_CHAT_ID=TON_CHAT_ID

SG_MAX_ATTEMPTS=3
SG_BAN_DURATION_SECONDS=86400

SG_WHITELIST=127.0.0.1,::1,TON_IP

SG_FIREWALL_ENABLED=false

SG_MFA_ENABLED=false
SG_MFA_TIMEOUT_SECONDS=45
SG_MFA_FAIL_MODE=deny

SG_MFA_BYPASS_USERS=
SG_MFA_BYPASS_IPS=
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

#### Durée de bannissement

```env
SG_BAN_DURATION_SECONDS=86400
```

`86400` secondes correspondent à :

```text
24 heures
```

---

## 🔐 Configuration MFA dans `.env`

### Activation MFA

```env
SG_MFA_ENABLED=false
```

Pour une installation neuve, il est recommandé de commencer avec :

```text
false
```

Une fois Telegram et le serveur vérifiés, le MFA peut être activé dynamiquement avec :

```text
/mfaon
```

### Timeout MFA

```env
SG_MFA_TIMEOUT_SECONDS=45
```

Cela représente le temps maximum pendant lequel une tentative SSH attend une décision.

Exemple :

```text
Clé SSH valide
      │
      ▼
Demande MFA
      │
      ├── décision reçue avant 45s → résultat appliqué
      │
      └── aucune décision → expired → connexion refusée
```

### Fail mode

```env
SG_MFA_FAIL_MODE=deny
```

`deny` est recommandé.

En cas de panne Redis ou du backend MFA :

```text
backend MFA inaccessible
        │
        ▼
connexion refusée
```

Cela évite qu'une panne de sécurité transforme automatiquement le MFA en accès libre.

### Bypass utilisateurs

```env
SG_MFA_BYPASS_USERS=
```

Exemple :

```env
SG_MFA_BYPASS_USERS=backup
```

### Bypass IP statiques

```env
SG_MFA_BYPASS_IPS=
```

Exemple :

```env
SG_MFA_BYPASS_IPS=10.0.0.10
```

Les bypass statiques doivent rester exceptionnels.

---

### 7. Redémarrer SSH Guardian

Après modification du `.env` :

```bash
sudo systemctl restart \
  ssh-guardian@collector \
  ssh-guardian@geoip \
  ssh-guardian@mfa \
  ssh-guardian@security \
  ssh-guardian@firewall \
  ssh-guardian@storage \
  ssh-guardian@control \
  ssh-guardian@telegram \
  ssh-guardian@api \
  ssh-guardian@panel
```

---

### 8. Vérifier l'installation

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
  ssh-guardian@mfa \
  ssh-guardian@security \
  ssh-guardian@firewall \
  ssh-guardian@storage \
  ssh-guardian@control \
  ssh-guardian@telegram \
  ssh-guardian@api \
  ssh-guardian@panel
```

Vérification rapide :

```bash
for service in \
  collector \
  geoip \
  mfa \
  security \
  firewall \
  storage \
  control \
  telegram \
  api \
  panel
do
    printf "%-12s : " "$service"
    systemctl is-active "ssh-guardian@$service"
done
```

Résultat attendu :

```text
collector    : active
geoip        : active
mfa          : active
security     : active
firewall     : active
storage      : active
control      : active
telegram     : active
api          : active
panel        : active
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
| `/mfa` | Afficher le menu MFA |
| `/mfastatus` | Afficher l'état MFA |
| `/mfaon` | Activer le MFA |
| `/mfaoff` | Désactiver le MFA |
| `/mfatimeout <secondes>` | Modifier le timeout MFA |
| `/mfaallow <IP> [durée]` | Autoriser temporairement une IP |
| `/mfarevoke <IP>` | Révoquer une autorisation temporaire |

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

Les notifications de ban peuvent inclure :

```text
🚫 IP bannie

IP : 203.0.113.10
Localisation : Paris, France
FAI : Example ISP

Raison : too_many_connection_attempts
Tentatives : 3
Durée : 24 h
Firewall : banned
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

Terminer toutes les sessions distantes :

```text
/killallsessions
```

⚠️ Vérifie toujours le PID avant de terminer une session.

---

# 🔐 MFA SSH avec approbation Telegram

Le MFA permet d'ajouter une deuxième validation après une clé publique SSH correcte.

Le fonctionnement général est :

```text
Connexion SSH
      │
      ▼
Clé publique
      │
      ├── invalide ───────────────────────► REFUS
      │
      ▼
Clé valide
      │
      ▼
keyboard-interactive / PAM
      │
      ▼
SSH Guardian MFA
      │
      ├── MFA désactivé ─────────────────► AUTORISÉ
      │
      ├── utilisateur bypass ─────────────► AUTORISÉ
      │
      ├── IP bypass statique ─────────────► AUTORISÉ
      │
      ├── IP autorisée temporairement ────► AUTORISÉ
      │
      └── validation nécessaire
              │
              ▼
        Demande MFA Redis
              │
              ▼
          Telegram
        ┌─────┴─────┐
        │           │
        ▼           ▼
   ✅ Autoriser  ❌ Refuser
        │           │
        ▼           ▼
     SSH OK      SSH refusé
```

---

## 🧩 Service MFA

Le MFA possède son propre microservice :

```text
services.mfa.app.main
```

Lancer manuellement pour diagnostic :

```bash
PYTHONPATH=. python3 \
  -m services.mfa.app.main
```

Exemple :

```text
SSH Guardian - MFA Service
Redis : True
Lecture : mfa.commands
Publication : mfa.events
MFA runtime : True
```

En production :

```bash
systemctl status ssh-guardian@mfa
```

---

## 🔗 PAM Bridge

OpenSSH ne contacte pas directement Telegram.

Il utilise PAM :

```text
OpenSSH
   │
   ▼
PAM
   │
   ▼
/usr/local/bin/ssh-guardian-mfa
   │
   ▼
services/mfa/bin/pam_bridge.py
```

Le wrapper :

```text
/usr/local/bin/ssh-guardian-mfa
```

charge automatiquement le `.env` du projet avant de lancer Python.

---

## 🔑 Configuration OpenSSH MFA

La configuration effective utilise notamment :

```text
UsePAM yes
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication yes
AuthenticationMethods publickey,keyboard-interactive:pam
```

Cela impose :

```text
Facteur 1 : clé SSH valide
Facteur 2 : keyboard-interactive / PAM / SSH Guardian
```

Vérification :

```bash
sshd -T | grep -Ei \
'^(usepam|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|authenticationmethods|forcecommand)'
```

---

## 📲 Notification MFA Telegram

Lors d'une connexion SSH nécessitant une validation, Telegram peut recevoir :

```text
🔐 DEMANDE DE CONNEXION SSH

Utilisateur : admin
IP : 82.80.219.126
Localisation : Maale Iron, Israel
FAI : Bezeq International Ltd.

En attente d'une décision...
```

Avec des boutons tels que :

```text
✅ Autoriser
❌ Refuser
```

Selon la version du bot et les options configurées, des actions d'autorisation temporaire peuvent également être proposées.

---

## ✅ Autoriser une connexion

Depuis Telegram :

```text
✅ Autoriser
```

La demande passe :

```text
pending
   │
   ▼
approved
```

Le bridge PAM voit la décision et retourne succès à OpenSSH.

La connexion SSH continue.

---

## ❌ Refuser une connexion

Telegram :

```text
❌ Refuser
```

La demande passe :

```text
pending
   │
   ▼
denied
```

Le bridge PAM refuse l'authentification SSH.

---

## ⌛ Expiration MFA

Si aucune décision n'arrive avant le timeout :

```text
pending
   │
   ▼
expired
```

La connexion SSH est refusée.

---

## 🟢 Activer le MFA

Telegram :

```text
/mfaon
```

Le changement est dynamique.

Il n'est pas nécessaire de modifier `sshd_config` ou de redémarrer SSH à chaque activation.

---

## 🔴 Désactiver le MFA

```text
/mfaoff
```

Lorsque le MFA runtime est désactivé :

```text
clé SSH valide
      │
      ▼
PAM bridge
      │
      ▼
MFA runtime OFF
      │
      ▼
AUTORISÉ
```

---

## 📊 Vérifier l'état MFA

```text
/mfastatus
```

ou :

```text
/mfa
```

L'état peut contenir notamment :

```text
MFA activé / désactivé
Timeout
Fail mode
Autorisations temporaires
```

---

## ⏱ Modifier le timeout MFA

Exemple :

```text
/mfatimeout 60
```

Le nouveau timeout devient :

```text
60 secondes
```

Le runtime accepte les modifications sans recharger OpenSSH.

---

## 🔓 Autorisation MFA temporaire

Une IP peut être autorisée temporairement.

Cela permet d'éviter une validation Telegram à chaque reconnexion depuis une IP de confiance.

### 15 minutes

```text
/mfaallow 203.0.113.10 15m
```

### 1 heure

```text
/mfaallow 203.0.113.10 1h
```

### 8 heures

```text
/mfaallow 203.0.113.10 8h
```

### 1 jour

```text
/mfaallow 203.0.113.10 1d
```

Le fonctionnement devient :

```text
Connexion
   │
   ▼
clé valide
   │
   ▼
IP temporairement autorisée ?
   │
   ├── NON ───► demander validation MFA
   │
   └── OUI ───► connexion autorisée
```

---

## 🔒 Révoquer une autorisation temporaire

```text
/mfarevoke 203.0.113.10
```

Après révocation :

```text
prochaine connexion
      │
      ▼
validation MFA nécessaire
```

---

## ⚙️ Runtime MFA

Le runtime permet de modifier le MFA sans éditer OpenSSH.

Il gère notamment :

```text
enabled
timeout
bypass temporaires
TTL
```

Les données runtime sont stockées dans Redis.

Exemples de clés :

```text
mfa:runtime:enabled
mfa:runtime:timeout
```

---

## 🧠 États d'une demande MFA

Une demande peut notamment être :

```text
pending
approved
denied
expired
cancelled
```

Une demande déjà décidée ne peut pas être approuvée une deuxième fois.

---

## 📡 Redis MFA

Streams :

```text
mfa.commands
mfa.events
```

Voir les derniers événements :

```bash
redis-cli --raw \
  XREVRANGE mfa.events + - COUNT 10
```

Exemple :

```json
{
  "request_id": "abc...",
  "username": "admin",
  "ip": "203.0.113.50",
  "status": "approved",
  "country": "France",
  "country_code": "FR",
  "city": "Paris",
  "isp": "Example ISP",
  "decision_source": "telegram",
  "event_type": "mfa.request.approved"
}
```

La source de décision peut permettre de distinguer par exemple :

```text
telegram
panel
api
```

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
✓ état MFA
✓ activation / désactivation MFA
✓ timeout MFA
✓ demandes MFA en attente
✓ approbation MFA
✓ refus MFA
✓ autorisation temporaire
✓ liste des bypass temporaires
✓ TTL des autorisations
✓ révocation d'une autorisation
```

### Module MFA du Panel

Le Panel MFA permet notamment de voir :

```text
🔐 MFA SSH

Protection MFA
● ACTIVE / DÉSACTIVÉE

Timeout
45 secondes

Autorisations temporaires
82.80.x.x — TTL restant

Demandes en attente
admin
82.80.x.x
ville
pays
FAI
```

Les actions disponibles peuvent inclure :

```text
Activer
Désactiver
Enregistrer le timeout
Autoriser
Refuser
Autoriser 15 min
Autoriser 1 h
Autoriser 8 h
Autoriser temporairement une IP
Révoquer
```

---

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

## 🔐 API MFA

L'API expose également des routes de gestion MFA.

### État MFA

```bash
curl -s \
  http://127.0.0.1:8080/mfa/status \
  | python3 -m json.tool
```

### Activer

```bash
curl -X POST \
  http://127.0.0.1:8080/mfa/enable
```

### Désactiver

```bash
curl -X POST \
  http://127.0.0.1:8080/mfa/disable
```

### Modifier le timeout

```bash
curl -X POST \
  http://127.0.0.1:8080/mfa/timeout/60
```

### Autoriser une IP pendant 1 heure

```bash
curl -X POST \
  "http://127.0.0.1:8080/mfa/allow-ip/203.0.113.10?duration=3600"
```

### Révoquer

```bash
curl -X POST \
  http://127.0.0.1:8080/mfa/revoke-ip/203.0.113.10
```

### Demandes MFA en attente

```bash
curl -s \
  "http://127.0.0.1:8080/mfa/requests?status=pending" \
  | python3 -m json.tool
```

### Autoriser une demande

```bash
curl -X POST \
  http://127.0.0.1:8080/mfa/request/REQUEST_ID/approve
```

### Autoriser temporairement une demande

```bash
curl -X POST \
  "http://127.0.0.1:8080/mfa/request/REQUEST_ID/approve-temporary?duration=3600"
```

### Refuser

```bash
curl -X POST \
  http://127.0.0.1:8080/mfa/request/REQUEST_ID/deny
```

---

## 🌐 API du Panel MFA

Le Panel relaie les actions vers l'API interne.

Exemples :

```text
GET  /api/mfa/status
GET  /api/mfa/requests?status=pending

POST /api/mfa/enable
POST /api/mfa/disable
POST /api/mfa/timeout/{seconds}

POST /api/mfa/allow-ip/{ip}
POST /api/mfa/revoke-ip/{ip}

POST /api/mfa/request/{id}/approve
POST /api/mfa/request/{id}/approve-temporary
POST /api/mfa/request/{id}/deny
```

Les routes du Panel sont protégées par le token du Panel.

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

Pour une authentification MFA :

```text
OpenSSH
   │
   ▼
PAM
   │
   ▼
MFA bridge
   │
   ▼
mfa.commands
   │
   ▼
MFA Service
   │
   ├──► mfa.events
   ├──► Telegram
   ├──► API
   └──► Panel
```

---

## 🧩 Services

SSH Guardian est composé de plusieurs services :

| Service | Rôle |
|---|---|
| `collector` | Lit les événements OpenSSH |
| `geoip` | Géolocalise les IP |
| `mfa` | Gère les demandes MFA, décisions, timeout et bypass temporaires |
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
│   ├── mfa/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── manager.py
│   │   │   ├── models.py
│   │   │   ├── runtime.py
│   │   │   └── service.py
│   │   └── bin/
│   │       └── pam_bridge.py
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

---

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
mfa.commands
mfa.events
```

Voir les derniers événements Security :

```bash
redis-cli XREVRANGE security.actions + - COUNT 10
```

MFA :

```bash
redis-cli XREVRANGE mfa.events + - COUNT 10
```

Control :

```bash
redis-cli XREVRANGE control.commands + - COUNT 10
```

Firewall :

```bash
redis-cli XREVRANGE firewall.events + - COUNT 10
```

---

## 📋 Logs

SSH Guardian utilise `journalctl` en production.

### Tous les services

```bash
./scripts/logs.sh
```

### Collector

```bash
journalctl -u ssh-guardian@collector -f
```

### GeoIP

```bash
journalctl -u ssh-guardian@geoip -f
```

### MFA

```bash
journalctl -u ssh-guardian@mfa -f
```

### Security

```bash
journalctl -u ssh-guardian@security -f
```

### Firewall

```bash
journalctl -u ssh-guardian@firewall -f
```

### Storage

```bash
journalctl -u ssh-guardian@storage -f
```

### Control

```bash
journalctl -u ssh-guardian@control -f
```

### Telegram

```bash
journalctl -u ssh-guardian@telegram -f
```

### API

```bash
journalctl -u ssh-guardian@api -f
```

### Panel

```bash
journalctl -u ssh-guardian@panel -f
```

### Logs OpenSSH

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
✓ création des demandes MFA
✓ persistance MFA
✓ lecture des demandes MFA
✓ approbation MFA
✓ refus MFA
✓ rejet d'une double approbation
✓ rejet d'une approbation après refus
✓ requêtes inconnues
✓ expiration MFA
✓ refus d'une approbation après expiration
```

Test MFA uniquement :

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_mfa.py \
  -v
```

---

## 🛠️ Développement

Démarrer :

```bash
./scripts/start-dev.sh
```

Les services DEV sont :

```text
collector
geoip
mfa
security
firewall
storage
control
telegram
api
panel
```

Le service MFA doit apparaître comme :

```text
mfa : ✅ RUNNING
```

Arrêter :

```bash
./scripts/stop-dev.sh
```

Voir les logs :

```bash
./scripts/logs.sh
```

En DEV, les services écrivent également dans :

```text
logs/collector.log
logs/geoip.log
logs/mfa.log
logs/security.log
logs/firewall.log
logs/storage.log
logs/control.log
logs/telegram.log
logs/api.log
logs/panel.log
```

> ⚠️ Ne lance pas simultanément le mode DEV et les mêmes services via systemd.

Cela provoquerait plusieurs instances d'un même consumer et pourrait produire des événements en double.

---

## 🚀 Production

En production, les services sont gérés par systemd :

```text
ssh-guardian@collector
ssh-guardian@geoip
ssh-guardian@mfa
ssh-guardian@security
ssh-guardian@firewall
ssh-guardian@storage
ssh-guardian@control
ssh-guardian@telegram
ssh-guardian@api
ssh-guardian@panel
```

Pour passer du DEV à la PROD :

```bash
./scripts/stop-dev.sh
```

Puis :

```bash
for service in \
  collector \
  geoip \
  mfa \
  security \
  firewall \
  storage \
  control \
  telegram \
  api \
  panel
do
    systemctl start "ssh-guardian@$service"
done
```

Vérifier :

```bash
for service in \
  collector \
  geoip \
  mfa \
  security \
  firewall \
  storage \
  control \
  telegram \
  api \
  panel
do
    printf "%-12s : " "$service"
    systemctl is-active "ssh-guardian@$service"
done
```

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

### MFA indisponible

```bash
systemctl status ssh-guardian@mfa
```

Logs :

```bash
journalctl \
  -u ssh-guardian@mfa \
  -n 100 \
  --no-pager
```

Tester le runtime :

```bash
curl -s \
  http://127.0.0.1:8080/mfa/status \
  | python3 -m json.tool
```

---

### Une demande MFA expire toujours

Vérifie :

```text
/mfastatus
```

Puis :

```bash
redis-cli XREVRANGE \
  mfa.events + - COUNT 10
```

Et :

```bash
journalctl \
  -u ssh-guardian@telegram \
  -n 100 \
  --no-pager
```

---

### Le MFA laisse passer alors qu'il devrait être actif

Vérifie `.env` :

```bash
grep '^SG_MFA_' .env
```

Puis l'état runtime :

```text
/mfastatus
```

Vérifie OpenSSH :

```bash
sshd -T | grep -Ei \
'^(usepam|kbdinteractiveauthentication|pubkeyauthentication|authenticationmethods)'
```

Attendu :

```text
usepam yes
pubkeyauthentication yes
kbdinteractiveauthentication yes
authenticationmethods publickey,keyboard-interactive:pam
```

---

### SSH demande un mot de passe inattendu

Vérifie :

```bash
sshd -T | grep -Ei \
'passwordauthentication|kbdinteractiveauthentication|authenticationmethods'
```

Le MFA SSH Guardian est conçu autour de :

```text
publickey,keyboard-interactive:pam
```

et non autour d'une authentification SSH classique par mot de passe.

---

### Vérifier PAM

```bash
grep -nE \
'pam_exec|pam_permit' \
/etc/pam.d/sshd
```

Le bridge doit apparaître :

```text
/usr/local/bin/ssh-guardian-mfa
```

---

### Tester le bridge PAM manuellement

Exemple :

```bash
PAM_USER=admin \
PAM_RHOST=203.0.113.50 \
PAM_SERVICE=sshd \
PAM_TYPE=auth \
/usr/local/bin/ssh-guardian-mfa

echo "EXIT=$?"
```

Retour :

```text
EXIT=0
```

signifie autorisé.

```text
EXIT=1
```

signifie refusé.

---

### Doubles événements SSH

Vérifie les processus :

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

Il ne doit pas y avoir simultanément :

```text
processus DEV
+
processus systemd
```

pour le même microservice.

Par exemple, un seul collector doit être actif.

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

Avant d'activer le MFA :

```text
✓ vérifier que la clé publique SSH fonctionne
✓ garder une deuxième connexion SSH ouverte
✓ vérifier Telegram
✓ vérifier le Chat ID
✓ tester le service mfa
✓ tester /mfastatus
✓ tester une demande réelle
✓ tester Autoriser
✓ tester Refuser
✓ tester l'expiration
✓ conserver SG_MFA_FAIL_MODE=deny en production
```

Puis activer :

```text
/mfaon
```

Et vérifier :

```text
/mfastatus
```

---

## 🔒 Sécurité de l'installation MFA

L'installation sauvegarde la configuration PAM/OpenSSH avant modification.

La configuration OpenSSH est testée avec :

```bash
sshd -t
```

Si la configuration MFA générée est invalide, le mécanisme d'installation peut restaurer la configuration précédente.

⚠️ Malgré cette protection, conserve toujours une session SSH ouverte lors d'une modification PAM/OpenSSH.

---

## 🛡️ Recorder SSH

SSH Guardian peut enregistrer les sessions interactives SSH via :

```text
/usr/local/bin/ssh-wrapper.sh
```

Les enregistrements sont stockés dans le répertoire configuré par :

```text
SG_SESSION_LOG_DIR
```

Les sessions peuvent ensuite être inspectées ou streamées via les fonctionnalités Control / Telegram.

---

## 🗑️ Désinstallation

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

---

## 🔐 Fichiers sensibles

Ne commit jamais :

```text
.env
tokens Telegram
Chat ID privé si nécessaire
token Panel
clés SSH privées
logs sensibles
enregistrements de sessions
```

---

<div align="center">

### 🛡️ SSH Guardian V2

**Un mini SOC dédié à la surveillance et à la protection de ton serveur SSH.**

`COLLECT` · `ENRICH` · `DETECT` · `MFA` · `BLOCK` · `NOTIFY`

</div>

<div align="center">

# 🛡️ SSH Guardian V2

### Surveillance SSH en temps réel, détection des menaces et réponse automatisée

**Un mini Security Operations Center (SOC) modulaire pour protéger et superviser les accès SSH d'un serveur Linux.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Debian%20%7C%20Ubuntu-FCC624?logo=linux&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-Services-000000?logo=linux&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)

<br>

**SURVEILLER · DÉTECTER · ENRICHIR · BLOQUER · NOTIFIER · INVESTIGUER**

</div>

---

## 📖 Présentation

**SSH Guardian V2** est une plateforme de sécurité conçue pour surveiller et protéger un serveur SSH en temps réel.

Le projet analyse l'activité OpenSSH du serveur afin de détecter notamment :

- les nouvelles connexions SSH ;
- les authentifications échouées ;
- les utilisateurs invalides ;
- les connexions interrompues avant authentification ;
- les authentifications réussies ;
- les adresses IP suspectes ;
- les attaques répétées ;
- les connexions provenant de pays bloqués.

Chaque adresse IP peut être enrichie avec :

- son pays ;
- son code ISO ;
- sa ville ;
- son fournisseur d'accès / ISP.

SSH Guardian peut ensuite :

- compter les tentatives ;
- bannir automatiquement une adresse IP ;
- bloquer des pays ;
- envoyer des alertes Telegram ;
- conserver l'historique dans SQLite ;
- afficher les événements dans un dashboard Web ;
- exposer une API HTTP ;
- afficher les sessions SSH actives ;
- terminer une session SSH ;
- inspecter les sessions enregistrées/streamables.

---

## 🏗️ Architecture

SSH Guardian n'est pas un script monolithique.

Il est composé de plusieurs services indépendants communiquant principalement avec **Redis Streams**.

```text
                         SERVEUR SSH
                              │
                              ▼
                        OpenSSH / journald
                              │
                              ▼
                         ┌───────────┐
                         │ Collector │
                         └─────┬─────┘
                               │
                          ssh.events
                               │
                               ▼
                            Redis
                               │
                               ▼
                         ┌───────────┐
                         │   GeoIP   │
                         └─────┬─────┘
                               │
                     ssh.events.enriched
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
          Security          Storage         Telegram
              │                │
              ▼                ▼
      security.actions       SQLite
              │
              ▼
          Firewall


          SQLite / Redis / Control
                    │
                    ▼
                   API
                    │
                    ▼
               Web Panel
```

---

## ✨ Fonctionnalités

| Fonction | Description |
|---|---|
| 🔍 Surveillance | Analyse en temps réel des événements OpenSSH |
| 🚨 Détection | Détection des connexions et authentifications suspectes |
| 🔢 Compteur | Comptage des tentatives par adresse IP |
| 🌍 GeoIP | Pays, ville, code ISO et fournisseur d'accès |
| 🔥 Firewall | Bannissement et débannissement d'adresses IP |
| 🌐 Blocage pays | Blocage automatique des connexions provenant d'un pays |
| 🛡️ Whitelist | Protection des adresses IP administratives |
| 📱 Telegram | Alertes et administration distante |
| 💻 Sessions | Consultation des sessions SSH actives |
| 📡 Stream | Consultation des sessions enregistrées |
| ☠️ Kill session | Fermeture d'une session SSH |
| 🗄️ SQLite | Historique persistant des événements |
| ⚡ Redis | Bus d'événements entre les services |
| 🔌 API | API HTTP FastAPI |
| 🖥️ Panel | Dashboard Web de supervision |
| ⚙️ systemd | Exécution des services en production |
| 🧪 Tests | Tests automatisés avec pytest |

---

# 🚀 Installation complète

Cette section est conçue pour permettre une installation depuis zéro.

Suivez simplement les étapes **dans l'ordre**.

---

## 1. Préparer un serveur

SSH Guardian est prévu principalement pour un serveur :

- Debian ou Ubuntu ;
- utilisant OpenSSH ;
- utilisant systemd ;
- disposant d'un accès Internet ;
- administrable avec `sudo` ou `root`.

L'installation nécessite des privilèges administrateur car SSH Guardian doit notamment configurer :

- OpenSSH ;
- systemd ;
- Redis ;
- le firewall ;
- l'enregistrement des sessions SSH.

> ⚠️ Ne fermez pas votre session SSH actuelle pendant l'installation.

Conserver une session ouverte permet de récupérer plus facilement le serveur en cas de mauvaise configuration SSH ou firewall.

---

# 📱 2. Créer le bot Telegram AVANT l'installation

Il est recommandé de préparer Telegram avant de lancer `install.sh`.

Vous aurez besoin de deux informations :

```text
SG_TELEGRAM_TOKEN
SG_TELEGRAM_CHAT_ID
```

---

## 2.1 Créer le bot

Dans Telegram, recherchez :

```text
@BotFather
```

Ouvrez la conversation puis envoyez :

```text
/newbot
```

BotFather demande ensuite un nom.

Exemple :

```text
SSH Guardian
```

Puis un nom d'utilisateur unique terminant généralement par `bot`.

Exemple :

```text
my_ssh_guardian_bot
```

BotFather fournit ensuite un token ressemblant à :

```text
1234567890:AA_EXAMPLE_TOKEN
```

Conservez-le.

Ce token deviendra :

```env
SG_TELEGRAM_TOKEN=1234567890:AA_EXAMPLE_TOKEN
```

> 🔐 Le token Telegram est un secret. Ne le publiez jamais dans GitHub, un README, une capture d'écran ou un fichier public.

---

## 2.2 Envoyer `/start` au bot

Ouvrez maintenant votre nouveau bot Telegram.

Cliquez sur **Start** ou envoyez :

```text
/start
```

Cette étape est importante : Telegram doit avoir au moins un message permettant de retrouver votre Chat ID.

---

## 2.3 Récupérer le Chat ID

Depuis votre serveur, remplacez la valeur ci-dessous par le token obtenu auprès de BotFather :

```bash
TOKEN="VOTRE_TOKEN_TELEGRAM"
```

Puis :

```bash
curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | python3 -m json.tool
```

Cherchez une section similaire à :

```json
"chat": {
    "id": 123456789,
    "first_name": "Jean",
    "type": "private"
}
```

La valeur :

```text
123456789
```

est votre **Chat ID**.

Elle deviendra :

```env
SG_TELEGRAM_CHAT_ID=123456789
```

Si `jq` est déjà installé, vous pouvez également utiliser :

```bash
curl -s \
  "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | jq '.result[-1].message.chat.id'
```

Vous disposez maintenant des deux informations nécessaires :

```text
Token Telegram
Chat ID Telegram
```

---

## 2.4 Vérifier le token Telegram

Avant d'aller plus loin :

```bash
curl -s \
  "https://api.telegram.org/bot${TOKEN}/getMe" \
  | python3 -m json.tool
```

Un token valide doit retourner notamment :

```json
{
    "ok": true
}
```

---

# 📦 3. Télécharger SSH Guardian

Clonez le dépôt GitHub :

```bash
git clone <URL_DU_DEPOT_GITHUB>
```

Entrez ensuite dans le projet :

```bash
cd SSH-GUARDIAN-
```

À partir de maintenant, toutes les commandes du README supposent que vous êtes dans :

```text
SSH-GUARDIAN-
```

---

# ⚙️ 4. Lancer l'installation

Rendez les scripts exécutables :

```bash
chmod +x install.sh uninstall.sh
```

Lancez ensuite :

```bash
sudo ./install.sh
```

L'installateur prépare automatiquement l'environnement nécessaire au projet.

Il s'occupe notamment de :

- vérifier le système ;
- installer/préparer les dépendances ;
- préparer Python ;
- vérifier les imports ;
- préparer Redis ;
- créer les répertoires nécessaires ;
- générer le fichier `.env` ;
- générer le token du Panel ;
- installer le système d'enregistrement SSH ;
- configurer OpenSSH ;
- vérifier la configuration avec `sshd -t` ;
- détecter le service OpenSSH ;
- installer les services systemd SSH Guardian ;
- préparer l'environnement d'exécution.

---

# 🔧 5. Compléter le fichier `.env`

**Il n'est pas nécessaire de créer `.env` manuellement.**

Le fichier :

```text
.env
```

est généré par :

```text
install.sh
```

Après l'installation, ouvrez simplement le fichier généré :

```bash
nano .env
```

Vous devez principalement compléter les informations qui dépendent de votre installation.

---

## Telegram

Renseignez les informations préparées avant l'installation :

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=VOTRE_TOKEN_TELEGRAM
SG_TELEGRAM_CHAT_ID=VOTRE_CHAT_ID
```

Exemple :

```env
SG_TELEGRAM_ENABLED=true
SG_TELEGRAM_TOKEN=1234567890:AA_EXAMPLE_TOKEN
SG_TELEGRAM_CHAT_ID=123456789
```

N'utilisez évidemment pas ces valeurs d'exemple.

---

## Whitelist

La whitelist empêche SSH Guardian de bannir certaines adresses de confiance.

Exemple :

```env
SG_WHITELIST=127.0.0.1,::1
```

Pour ajouter votre IP publique :

```env
SG_WHITELIST=127.0.0.1,::1,VOTRE_IP
```

Plusieurs adresses sont séparées par des virgules.

> ⚠️ Vérifiez soigneusement la whitelist avant d'activer réellement le firewall.

---

## Nombre de tentatives

Exemple :

```env
SG_MAX_ATTEMPTS=3
```

Avec cette configuration :

```text
Tentative 1/3 → surveillance
Tentative 2/3 → surveillance
Tentative 3/3 → bannissement
```

---

## Durée du bannissement

Exemple :

```env
SG_BAN_DURATION_SECONDS=86400
```

Valeurs utiles :

| Durée | Secondes |
|---|---:|
| 1 heure | `3600` |
| 6 heures | `21600` |
| 12 heures | `43200` |
| 24 heures | `86400` |
| 7 jours | `604800` |

---

## Firewall

Pendant les premiers tests, utilisez :

```env
SG_FIREWALL_ENABLED=false
```

Le système détectera les événements sans appliquer réellement les bannissements.

Lorsque vous êtes certain que :

- votre IP est dans la whitelist ;
- Telegram fonctionne ;
- la détection fonctionne ;
- les événements sont correctement remontés ;

vous pouvez activer :

```env
SG_FIREWALL_ENABLED=true
```

> ⚠️ Une mauvaise whitelist combinée à un firewall actif peut bloquer votre propre accès SSH.

---

# 🔐 6. Token du Panel

Le dashboard Web est protégé par :

```env
SG_PANEL_TOKEN=
```

Le token est généré automatiquement par `install.sh`.

Vous n'avez normalement rien à créer manuellement.

Pour afficher le token généré :

```bash
grep '^SG_PANEL_TOKEN=' .env
```

Pour afficher uniquement sa valeur :

```bash
grep '^SG_PANEL_TOKEN=' .env \
  | cut -d= -f2-
```

Conservez ce token privé.

Il permet d'accéder aux fonctions administratives du Panel.

---

# 🔄 7. Appliquer la configuration

Après avoir complété `.env`, redémarrez les services SSH Guardian :

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

# ✅ 8. Vérifier que SSH Guardian fonctionne

Vérifiez tous les services :

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

Chaque service doit normalement apparaître :

```text
active (running)
```

---

## Vérifier Redis

```bash
redis-cli ping
```

Résultat attendu :

```text
PONG
```

---

## Vérifier l'API

```bash
curl -s http://127.0.0.1:8080/health \
  | python3 -m json.tool
```

---

## Vérifier les ports

```bash
ss -lntp | grep -E ':3000|:8080'
```

Vous devez normalement retrouver :

```text
127.0.0.1:8080
```

pour l'API et le port `3000` utilisé par le Panel selon sa configuration.

---

# 📱 9. Tester Telegram

Envoyez au bot :

```text
/stats
```

Vous pouvez ensuite tester :

```text
/top
```

puis :

```text
/topcountries
```

et :

```text
/countries
```

Si le bot répond, la communication Telegram fonctionne.

---

# 🖥️ 10. Accéder au Panel Web

Le Panel utilise par défaut le port :

```text
3000
```

Pour éviter d'exposer inutilement l'interface d'administration sur Internet, il est recommandé de l'utiliser via un **tunnel SSH**.

Depuis votre ordinateur :

```bash
ssh -i CHEMIN_VERS_VOTRE_CLE \
  -N \
  -L 3000:127.0.0.1:3000 \
  UTILISATEUR@VOTRE_SERVEUR
```

Sous Windows PowerShell, le principe est identique :

```powershell
ssh -i "CHEMIN_VERS_VOTRE_CLE.pem" -N -L 3000:127.0.0.1:3000 UTILISATEUR@VOTRE_SERVEUR
```

Gardez cette fenêtre ouverte.

Ouvrez ensuite votre navigateur sur :

```text
http://127.0.0.1:3000
```

Lorsque le Panel demande son token, récupérez-le avec :

```bash
grep '^SG_PANEL_TOKEN=' .env \
  | cut -d= -f2-
```

---

# 🎉 Installation terminée

À ce stade, vous devez avoir :

```text
✅ OpenSSH surveillé
✅ Redis opérationnel
✅ Collector actif
✅ Enrichissement GeoIP actif
✅ Security Engine actif
✅ Firewall prêt
✅ SQLite actif
✅ Control actif
✅ Telegram actif
✅ API active
✅ Panel actif
✅ Token Panel configuré
```

Vous pouvez maintenant utiliser SSH Guardian.

---

# 📱 Commandes Telegram

## Informations

| Commande | Fonction |
|---|---|
| `/stats` | Statistiques globales |
| `/top` | IP les plus actives |
| `/topcountries` | Pays générant le plus d'activité suspecte |
| `/search <IP>` | Historique d'une adresse IP |
| `/bans` | Bans actifs |
| `/countries` | Pays actuellement bloqués |

---

## Firewall

Débannir une adresse :

```text
/unban 203.0.113.10
```

Bloquer un pays :

```text
/block fr
```

Débloquer un pays :

```text
/unblock fr
```

Afficher les pays bloqués :

```text
/countries
```

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

---

## Sessions SSH

Afficher les sessions :

```text
/sessions
```

ou :

```text
/active
```

Exemple de résultat :

```text
Sessions SSH actives

PID : 151658
Utilisateur : admin
IP : 203.0.113.20
TTY : pts/0
LIVE / streamable
```

Consulter une session :

```text
/stream 151658
```

Terminer cette session :

```text
/killsession 151658
```

Terminer les sessions distantes gérées :

```text
/killallsessions
```

> ⚠️ Vérifiez toujours le PID et la session avant d'utiliser une commande de terminaison.

---

# 🚨 Exemple de détection

Une activité SSH suspecte peut produire une notification similaire à :

```text
🚨 Tentative SSH échouée

IP : 201.214.43.22
Localisation : Quillota, Chile
FAI : VTR BANDA ANCHA S.A.

Raison : connexion fermée avant authentification

Tentatives : 1/3
Avant bannissement : 2
```

Puis :

```text
Tentatives : 2/3
Avant bannissement : 1
```

Lorsque le seuil configuré est atteint, le Security Engine peut générer une action de bannissement transmise au Firewall.

---

# 🌍 Blocage par pays

SSH Guardian peut interdire automatiquement les nouvelles connexions provenant d'un pays.

Depuis Telegram :

```text
/block fr
```

Pour débloquer :

```text
/unblock fr
```

Pour afficher la configuration :

```text
/countries
```

Les mêmes opérations peuvent être réalisées depuis le Panel Web.

---

# 🔎 Recherche d'une IP

Depuis Telegram :

```text
/search 203.0.113.10
```

Le système peut utiliser l'historique enregistré afin d'afficher les informations connues sur cette adresse.

---

# 🖥️ Dashboard

Le dashboard constitue l'interface SOC de SSH Guardian.

Il permet notamment de consulter :

- l'état des services ;
- le nombre de connexions ;
- les échecs ;
- les succès ;
- les IP uniques ;
- les bans ;
- les événements récents ;
- les IP les plus actives ;
- les pays les plus actifs ;
- les pays bloqués ;
- les sessions SSH ;
- les opérations administratives.

---

# 🔌 API HTTP

L'API fonctionne par défaut sur :

```text
127.0.0.1:8080
```

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

# 🗄️ Base SQLite

L'historique est enregistré dans :

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

Rechercher une IP :

```sql
SELECT
    event_type,
    ip,
    country,
    city,
    timestamp
FROM enriched_events
WHERE ip = '203.0.113.10'
ORDER BY id DESC;
```

Quitter SQLite :

```text
.quit
```

---

# ⚡ Redis Streams

Redis constitue le bus d'événements interne.

Principaux streams :

```text
ssh.events
ssh.events.enriched
security.actions
firewall.events
control.commands
```

Vérifier Redis :

```bash
redis-cli ping
```

Compter les événements :

```bash
redis-cli XLEN ssh.events
redis-cli XLEN ssh.events.enriched
redis-cli XLEN security.actions
redis-cli XLEN firewall.events
```

Afficher les derniers événements :

```bash
redis-cli XREVRANGE ssh.events + - COUNT 10
```

---

# ⚙️ Gestion des services

Exemple avec Security :

```bash
systemctl status ssh-guardian@security
```

Redémarrer :

```bash
sudo systemctl restart ssh-guardian@security
```

Arrêter :

```bash
sudo systemctl stop ssh-guardian@security
```

Démarrer :

```bash
sudo systemctl start ssh-guardian@security
```

Logs en direct :

```bash
journalctl -u ssh-guardian@security -f
```

---

## Tous les services

SSH Guardian utilise notamment :

```text
ssh-guardian@collector
ssh-guardian@geoip
ssh-guardian@security
ssh-guardian@firewall
ssh-guardian@storage
ssh-guardian@control
ssh-guardian@telegram
ssh-guardian@api
ssh-guardian@panel
```

---

# 📋 Logs

Collector :

```bash
journalctl -u ssh-guardian@collector -f
```

GeoIP :

```bash
journalctl -u ssh-guardian@geoip -f
```

Security :

```bash
journalctl -u ssh-guardian@security -f
```

Firewall :

```bash
journalctl -u ssh-guardian@firewall -f
```

Storage :

```bash
journalctl -u ssh-guardian@storage -f
```

Control :

```bash
journalctl -u ssh-guardian@control -f
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

---

# 🔍 Logs OpenSSH

Selon le système, le service peut s'appeler `ssh` ou `sshd`.

Debian/Ubuntu utilise généralement :

```bash
journalctl -u ssh -f
```

Sur un système utilisant `sshd.service` :

```bash
journalctl -u sshd -f
```

Pour vérifier :

```bash
systemctl status ssh --no-pager 2>/dev/null || \
systemctl status sshd --no-pager
```

---

# 🧪 Tests

Lancez les tests depuis la racine du projet :

```bash
PYTHONPATH=. python3 -m pytest -q
```

La suite couvre notamment :

- le parsing des logs OpenSSH ;
- les événements de connexion ;
- les authentifications échouées ;
- les utilisateurs invalides ;
- GeoIP ;
- le Security Engine ;
- les compteurs ;
- le bannissement ;
- la whitelist ;
- le firewall ;
- SQLite.

---

# 🧑‍💻 Mode développement

Pour lancer la stack en mode développement :

```bash
./scripts/start-dev.sh
```

Pour l'arrêter :

```bash
./scripts/stop-dev.sh
```

Afficher les logs :

```bash
./scripts/logs.sh
```

> ⚠️ N'exécutez pas simultanément une instance DEV et la même instance gérée par systemd.

---

# ⚠️ Telegram : erreur 409 Conflict

Si vous voyez :

```text
409 Conflict
```

sur `getUpdates`, plusieurs processus utilisent probablement le même bot Telegram simultanément.

Vérifiez :

```bash
ps -ef | grep '[s]ervices.telegram.app.main'
```

En production, une seule instance Telegram doit être active.

Vous pouvez également vérifier systemd :

```bash
systemctl status ssh-guardian@telegram
```

---

# ⚠️ Port API déjà utilisé

```bash
ss -lntp | grep ':8080'
```

Puis :

```bash
ps -ef | grep '[s]ervices.api.app.main'
```

Évitez d'exécuter simultanément :

```text
API DEV
+
API systemd
```

---

# ⚠️ Port Panel déjà utilisé

```bash
ss -lntp | grep ':3000'
```

Puis :

```bash
ps -ef | grep '[s]ervices.panel.app.main'
```

---

# ⚠️ Telegram ne répond pas

Vérifiez le service :

```bash
systemctl status ssh-guardian@telegram
```

Puis :

```bash
journalctl -u ssh-guardian@telegram -n 100 --no-pager
```

Vérifiez également votre `.env` :

```bash
grep '^SG_TELEGRAM_' .env
```

Ne publiez pas la sortie si elle contient votre véritable token.

---

# ⚠️ Redis ne répond pas

```bash
redis-cli ping
```

Résultat attendu :

```text
PONG
```

Vérifiez le service :

```bash
systemctl status redis-server --no-pager
```

---

# 🔬 Diagnostic complet

Afficher les processus SSH Guardian :

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

Afficher les ports :

```bash
ss -lntp | grep -E ':3000|:8080'
```

Afficher les dernières actions Security :

```bash
redis-cli XREVRANGE security.actions + - COUNT 10
```

Afficher les événements Firewall :

```bash
redis-cli XREVRANGE firewall.events + - COUNT 10
```

Afficher les commandes Control :

```bash
redis-cli XREVRANGE control.commands + - COUNT 10
```

---

# 🔒 Recommandations de sécurité

Avant d'activer SSH Guardian en production :

1. gardez une session SSH ouverte pendant la configuration ;
2. ajoutez votre IP administrative à `SG_WHITELIST` ;
3. commencez avec `SG_FIREWALL_ENABLED=false` ;
4. vérifiez les événements SSH ;
5. vérifiez GeoIP ;
6. vérifiez les compteurs de tentatives ;
7. testez Telegram ;
8. testez le Panel ;
9. testez les opérations de déblocage ;
10. vérifiez que l'API reste privée ;
11. protégez le token du Panel ;
12. protégez le token Telegram ;
13. ne lancez pas plusieurs instances du même service ;
14. activez ensuite le firewall réel.

---

# 🔐 Secrets et Git

Ne publiez jamais :

```text
.env
clés SSH privées
token Telegram
token du Panel
bases contenant des données opérationnelles
logs de production
```

Le fichier :

```text
.env.example
```

peut rester dans Git.

Il sert uniquement de documentation des variables disponibles.

Le véritable :

```text
.env
```

est généré par l'installation et contient les secrets de la machine.

---

# 🗂️ Structure du projet

```text
SSH-GUARDIAN-/
│
├── services/
│   ├── collector/       Collecte OpenSSH / journald
│   ├── geoip/           Enrichissement GeoIP
│   ├── security/        Moteur de sécurité
│   ├── firewall/        Application des bannissements
│   ├── storage/         Persistance des événements
│   ├── control/         Commandes administratives
│   ├── telegram/        Bot Telegram
│   ├── api/             API FastAPI
│   └── panel/           Dashboard Web
│
├── shared/
│   ├── bus/             Communication Redis
│   ├── config/          Configuration partagée
│   └── events/          Modèles d'événements
│
├── scripts/             Scripts d'administration/dev
├── tests/               Tests automatisés
├── data/                Données persistantes
├── logs/                Logs du mode développement
├── run/                 PID du mode développement
│
├── install.sh           Installation automatique
├── uninstall.sh         Désinstallation
├── .env.example         Exemple de configuration
├── requirements.txt     Dépendances Python
└── README.md
```

---

# 🗑️ Désinstallation

Pour désinstaller SSH Guardian :

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

> ⚠️ Vérifiez le contenu du script de désinstallation avant son exécution si vous souhaitez conserver des données, des enregistrements de sessions ou certaines règles firewall.

---

# 🧠 Stack technique

<div align="center">

| Composant | Technologie |
|---|---|
| Runtime | Python |
| Serveur SSH | OpenSSH |
| Logs système | journald |
| Bus d'événements | Redis Streams |
| Base de données | SQLite |
| API | FastAPI |
| Dashboard | HTML / CSS / JavaScript |
| Notifications | Telegram Bot API |
| Firewall | Linux / iptables |
| Services | systemd |
| Tests | pytest |

</div>

---

# 🛡️ Philosophie du projet

SSH Guardian repose sur quatre principes.

**Observable**  
L'activité SSH doit être visible, enregistrée et exploitable.

**Modulaire**  
La collecte, l'enrichissement, la détection, le firewall et les interfaces sont séparés.

**Défensif**  
Les décisions de blocage proviennent du Security Engine et les adresses administratives peuvent être protégées par whitelist.

**Privé par défaut**  
Les interfaces administratives doivent rester aussi peu exposées que possible.

---

<div align="center">

## 🛡️ SSH Guardian V2

**De simples logs OpenSSH à une supervision de sécurité complète.**

`COLLECT` · `ENRICH` · `DETECT` · `BLOCK` · `NOTIFY` · `INVESTIGATE`

<br>

**Conçu pour les serveurs Linux utilisant OpenSSH.**

</div>

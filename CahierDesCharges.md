# Cahier des charges technique — SSH Guardian V2

## 1. Présentation générale

**SSH Guardian V2** est une plateforme de supervision et de protection SSH construite sous forme de services Python indépendants.

Son rôle est de surveiller en temps réel l’activité du serveur SSH, transformer les logs système en événements structurés, géolocaliser les adresses IP, détecter les comportements hostiles, appliquer des bannissements réseau, conserver l'historique, fournir des commandes d'administration, envoyer des notifications Telegram et exposer l'ensemble au travers d'une API et d'un dashboard Web.

L'architecture actuelle contient :

```text
OpenSSH / journald
       │
       ▼
┌───────────────┐
│   Collector   │
└───────┬───────┘
        │ ssh.events
        ▼
      Redis
        │
        ▼
┌───────────────┐
│     GeoIP     │
└───────┬───────┘
        │ ssh.events.enriched
        ▼
      Redis
        │
        ├──────────────► Security
        │                    │
        │                    ▼
        │              security.actions
        │                    │
        │                    ▼
        │                Firewall
        │
        ├──────────────► Storage ─────► SQLite
        │
        └──────────────► Telegram

SQLite / Control
        │
        ▼
       API
        │
        ▼
      Panel
```

Le projet est donc **événementiel** : les composants n'ont pas besoin d'être fortement couplés entre eux.

---

# 2. Arborescence générale

Le projet est actuellement organisé ainsi : 

```text
ssh-guardian-v2/
│
├── install.sh
├── uninstall.sh
├── requirements.txt
│
├── data/
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

Cette séparation est importante.

`services/` contient la logique métier.

`shared/` contient les composants utilisés par plusieurs services.

`data/` contient les données persistantes.

`logs/` contient les journaux applicatifs.

`run/` contient l'état des processus lancés en mode développement.

`scripts/` fournit les outils d'exploitation.

`tests/` protège les fonctions importantes contre les régressions.

---

# 3. Principe architectural fondamental

SSH Guardian ne doit pas être pensé comme :

```text
un gros script Python qui surveille SSH
```

mais comme :

```text
une chaîne de traitement d'événements
```

Une tentative SSH traverse plusieurs étapes.

Exemple :

```text
Internet
   │
   │ connexion TCP :22
   ▼
OpenSSH
   │
   │ journalctl
   ▼
Collector
   │
   │ SSHEvent
   ▼
Redis
   │
   ▼
GeoIP
   │
   │ SSHEvent enrichi
   ▼
Redis
   │
   ├────► Security
   │
   ├────► Storage
   │
   └────► Telegram
```

Cela permet notamment d'ajouter plus tard d'autres consommateurs sans réécrire le collecteur.

---

# 4. `services/collector`

Le service Collector contient actuellement :

```text
services/collector/app/
├── __init__.py
├── journal_reader.py
├── main.py
└── parser.py
```



## `journal_reader.py`

C'est l'interface entre SSH Guardian et `journald`.

Son objectif est de suivre les événements produits par OpenSSH, typiquement l'équivalent de :

```bash
journalctl -u ssh -f -n 0 --no-pager
```

Il doit transmettre chaque nouvelle ligne au parser.

Il ne devrait idéalement contenir aucune logique de sécurité.

Son travail est :

```text
journal SSH
    ↓
ligne brute
    ↓
parser
```

---

# 5. `services/collector/app/parser.py`

Le parser transforme les messages OpenSSH en événements compréhensibles par le reste de SSH Guardian.

Exemple brut :

```text
Connection from 201.214.43.22 port 12345
```

devient conceptuellement :

```text
event_type = ssh.connection.opened
ip = 201.214.43.22
```

Un message :

```text
Failed publickey for admin from 1.2.3.4
```

devient :

```text
ssh.login.failed
```

Un utilisateur inexistant :

```text
Invalid user toto from 1.2.3.4
```

devient :

```text
ssh.login.invalid_user
```

Une authentification correcte :

```text
Accepted publickey for admin from 1.2.3.4
```

devient :

```text
ssh.login.success
```

Le parser gère également les événements de connexion fermée/reset que nous avons utilisés pour détecter les connexions abandonnées avant authentification.

---

# 6. Notion importante : connexion ≠ authentification

C'est un point essentiel du système.

Un :

```text
ssh.connection.opened
```

ne signifie PAS :

```text
utilisateur authentifié
```

Il signifie seulement qu'un client est arrivé sur le serveur SSH.

La séquence peut être :

```text
connection.opened
        ↓
login.failed
        ↓
connection.reset
```

ou :

```text
connection.opened
        ↓
login.success
```

ou encore :

```text
connection.opened
        ↓
connection.closed
```

C'est précisément cette dernière situation qui nous a amenés à considérer une connexion fermée avant authentification comme une tentative infructueuse.

---

# 7. `shared/events/ssh.py`

Le modèle commun SSH se trouve dans :

```text
shared/events/ssh.py
```

Le fichier existe actuellement et constitue le contrat de données entre les services. 

Conceptuellement, un événement contient des informations telles que :

```text
event_type
timestamp
ip
username
```

puis, après GeoIP :

```text
country
country_code
city
isp
```

L'intérêt d'avoir un objet commun est d'éviter que :

```text
Collector
Security
GeoIP
Storage
Telegram
```

interprètent chacun les données différemment.

---

# 8. `shared/bus/redis_bus.py`

Le bus Redis est central dans l'architecture. Le tree confirme `shared/bus/redis_bus.py`. 

Son rôle est d'abstraire Redis.

Au lieu d'écrire partout :

```python
redis.xadd(...)
redis.xread(...)
```

les services passent par une interface commune.

Le principe est :

```text
service
   │
   ▼
RedisBus
   │
   ▼
Redis Streams
```

---

# 9. Streams Redis

Les principaux flux utilisés dans l'architecture sont notamment :

```text
ssh.events
ssh.events.enriched
security.actions
firewall.events
```

## `ssh.events`

Produit par Collector.

Contient les événements SSH interprétés mais pas encore enrichis.

---

## `ssh.events.enriched`

Produit par GeoIP.

Exemple conceptuel :

```json
{
  "event_type": "ssh.connection.opened",
  "ip": "201.214.43.22",
  "country": "Chile",
  "country_code": "CL",
  "city": "Quillota",
  "isp": "VTR BANDA ANCHA S.A."
}
```

---

## `security.actions`

Produit par Security.

Il représente une décision.

Par exemple :

```text
monitor
```

ou :

```text
ban_ip
```

---

## `firewall.events`

Retour du Firewall après exécution d'une action.

Exemple :

```text
IP demandée à bannir
        ↓
Security
        ↓
ban_ip
        ↓
Firewall
        ↓
iptables
        ↓
firewall.ip.banned
```

---

# 10. `services/geoip`

Le service contient : 

```text
services/geoip/app/
├── main.py
└── provider.py
```

## `provider.py`

Responsable de la résolution :

```text
IP
 ↓
GeoIP
 ↓
country
country_code
city
ISP
```

Exemple observé :

```text
201.214.43.22
    ↓
Chile
CL
Quillota
VTR BANDA ANCHA S.A.
```

Le provider isole la technologie GeoIP du reste de l'application.

Ainsi, le reste du projet n'a pas besoin de savoir comment l'information a été obtenue.

---

# 11. `geoip/app/main.py`

C'est le processus GeoIP permanent.

Il consomme :

```text
ssh.events
```

et publie :

```text
ssh.events.enriched
```

Le principe :

```text
Redis
  │
  │ ssh.events
  ▼
GeoIP
  │
  ├── recherche localisation
  ├── pays
  ├── code pays
  ├── ville
  └── FAI
  │
  ▼
ssh.events.enriched
```

---

# 12. `services/security`

Il contient actuellement : 

```text
services/security/app/
├── engine.py
├── main.py
└── rules.py
```

C'est le cerveau de détection.

---

# 13. `security/rules.py`

Ce fichier représente les paramètres des règles de sécurité.

Nous avons notamment travaillé avec :

```text
max_attempts = 3
```

et une durée de bannissement.

La séparation permet de ne pas enfouir les valeurs métier directement dans le moteur.

---

# 14. `security/engine.py`

`SecurityEngine` décide quoi faire d'un événement.

Son état conceptuel comprend :

```text
attempts[ip]
banned_until[ip]
```

Une IP peut passer par :

```text
tentative 1
   ↓
monitor
1/3

tentative 2
   ↓
monitor
2/3

tentative 3
   ↓
ban_ip
3/3
```

Après le bannissement, le moteur évite normalement d'émettre continuellement de nouvelles demandes de ban pour la même IP pendant la période concernée.

---

# 15. Whitelist

La whitelist est prioritaire.

Nous avons notamment configuré une variable du type :

```text
SG_WHITELIST=...
```

Lorsqu'une IP est whitelistée :

```text
événement
   ↓
SecurityEngine
   ↓
WHITELIST ?
   │
  OUI
   ↓
ignore
```

Elle ne doit donc pas être bannie par les règles classiques.

---

# 16. Échecs SSH

Le système doit actuellement reconnaître plusieurs formes d'échec :

```text
ssh.login.failed
ssh.login.invalid_user
ssh.connection.closed
ssh.connection.reset
```

Mais une distinction technique reste importante.

Un `connection.reset` après un `login.failed` peut représenter **la même tentative réseau**.

Par conséquent :

```text
login.failed
connection.reset
```

ne devraient pas nécessairement compter comme deux attaques différentes.

C'est actuellement l'un des principaux points d'amélioration architecturale : créer une notion de **tentative SSH normalisée**.

---

# 17. Blocage par pays

Nous avons ajouté un comportement particulier.

La commande :

```text
/block it
```

ajoute l'Italie aux pays interdits.

Lorsqu'une nouvelle IP est détectée :

```text
ssh.connection.opened
        ↓
GeoIP
        ↓
country_code = IT
        ↓
Security
        ↓
IT appartient aux pays bloqués ?
        ↓
       OUI
        ↓
ban_ip immédiatement
```

Le but est de bloquer l'IP **avant l'authentification**, et non d'attendre trois mots de passe incorrects.

---

# 18. Pourquoi nous n'avons finalement pas dépendu uniquement des plages IP pays

Au départ, `country_blocker.sh` téléchargeait des plages réseau d'un pays et les ajoutait à un `ipset`.

Le problème rencontré était concret :

```text
95.174.64.122
```

était identifié comme :

```text
Milan, Italy
```

mais :

```bash
ipset test blocked_countries 95.174.64.122
```

répondait :

```text
NOT in set
```

Donc les données de plages IP externes et la géolocalisation utilisée par Guardian pouvaient diverger.

La stratégie applicative GeoIP permet alors :

```text
IP observée
   ↓
géolocalisation réelle utilisée par Guardian
   ↓
country_code
   ↓
comparaison avec liste pays
   ↓
ban individuel
```

---

# 19. `country_blocker.sh`

Le fichier est situé ici :

```text
services/control/bin/country_blocker.sh
```

et une sauvegarde existe également. 

Il gère les opérations :

```bash
country_blocker.sh block it
country_blocker.sh unblock it
country_blocker.sh list
```

Il utilise notamment :

```text
iptables
ipset
wget
```

Le fichier de suivi des pays permet de conserver la liste logique des pays bloqués.

---

# 20. `services/firewall`

Le service contient : 

```text
services/firewall/app/
├── firewall.py
└── main.py
```

## `firewall.py`

C'est l'abstraction du firewall Linux.

Les opérations principales sont :

```text
ban(ip)
unban(ip)
```

Cela évite que Security ou Telegram exécutent eux-mêmes directement des commandes `iptables`.

Architecture :

```text
Security
   ↓
action logique
   ↓
Firewall
   ↓
iptables
```

---

# 21. DRY-RUN

Le Firewall supporte un mode de simulation.

Lorsque le firewall est désactivé :

```text
SG_FIREWALL_ENABLED=false
```

une demande de ban peut retourner :

```text
dry_run
```

sans modifier `iptables`.

Lorsque :

```text
SG_FIREWALL_ENABLED=true
```

les règles sont réellement appliquées.

C'est ce qui expliquait précédemment :

```text
Firewall en DRY-RUN
Action simulée
```

---

# 22. `firewall/app/main.py`

Le service permanent consomme les décisions de Security.

Exemple :

```text
security.actions
       ↓
Firewall Service
       ↓
action == ban_ip
       ↓
Firewall.ban(ip)
       ↓
iptables DROP
       ↓
firewall.events
```

---

# 23. `services/database`

Le projet possède également une couche base de données séparée : 

```text
services/database/app/
├── ban_manager.py
└── repository.py
```

## `repository.py`

Centralise les opérations SQLite propres à cette couche.

## `ban_manager.py`

Gère la logique liée aux bans persistants.

L'intérêt est de séparer :

```text
décision de sécurité
```

de :

```text
persistance du bannissement
```

---

# 24. `services/storage`

Le service Storage contient : 

```text
services/storage/app/
├── main.py
└── repository.py
```

Storage est l'archiviste du système.

Il écoute les différents streams et écrit les événements dans SQLite.

---

# 25. Base SQLite

La base actuelle est :

```text
data/guardian.db
```

avec ses fichiers WAL : 

```text
guardian.db
guardian.db-shm
guardian.db-wal
```

Cela indique l'utilisation du mode WAL de SQLite.

Le WAL est intéressant ici parce qu'il permet une meilleure coexistence entre :

```text
Storage → écritures
API → lectures
Control → lectures
```

---

# 26. `enriched_events`

Cette table est fondamentale pour les statistiques.

Elle contient notamment les événements enrichis :

```text
event_type
timestamp
ip
username
country
country_code
city
isp
...
```

C'est cette table que nous avons interrogée avec :

```sql
SELECT ...
FROM enriched_events
WHERE ...
```

---

# 27. Calcul des IP attaquantes

Nous avons corrigé la requête pour prendre en compte :

```sql
WHERE event_type IN (
    'ssh.login.failed',
    'ssh.login.invalid_user',
    'ssh.connection.closed',
    'ssh.connection.reset'
)
```

Puis :

```sql
GROUP BY ip
ORDER BY attempts DESC
```

Ce qui produit par exemple :

```text
82.80.219.126   8
45.128.39.115   6
201.214.43.22   2
```

---

# 28. Top pays

Même principe :

```sql
GROUP BY
    country,
    country_code
```

permet d'obtenir :

```text
Israel       8
Spain        8
Italy        3
Azerbaijan   2
Chile        2
...
```

Le problème que nous venons de diagnostiquer provenait d'une API encore chargée avec l'ancien code, alors que SQLite contenait déjà les bonnes données.

---

# 29. `services/control`

Le service est plus conséquent : 

```text
services/control/app/
├── country_manager.py
├── main.py
├── manager.py
├── session_manager.py
└── session_stream.py
```

Il constitue la couche administrative du système.

---

# 30. `control/app/manager.py`

C'est le gestionnaire général des commandes.

Il porte notamment la logique nécessaire aux fonctions administratives telles que :

```text
ban
unban
stats
top
topcountries
search
...
```

L'objectif est que Telegram ou une autre interface n'aient pas besoin de connaître directement SQLite, iptables ou Redis.

Architecture :

```text
Telegram
    ↓
Control
    ↓
Manager
    ├── DB
    ├── Firewall
    ├── Redis
    └── autres managers
```

---

# 31. `country_manager.py`

Ce composant encapsule toute la logique spécifique aux pays.

Nous avons travaillé directement dessus.

Il fournit conceptuellement :

```text
block(country)
unblock(country)
countries()
get_country_banned_ips()
```

Lors d'un `/unblock IT`, le comportement attendu est plus complexe que simplement enlever `IT` de la liste.

Il doit :

```text
/unblock IT
      ↓
retirer IT des pays interdits
      ↓
rechercher les IP bannies
pour reason=blocked_country
et country_code=IT
      ↓
Firewall.unban(ip)
      ↓
publication firewall.ip.unbanned
```

C'est ce qui permet de réellement libérer les IP italiennes déjà bannies.

---

# 32. `session_manager.py`

Ce composant est dédié aux sessions SSH.

Son existence sépare correctement :

```text
gestion des bans
```

de :

```text
gestion des sessions actives
```

Il est destiné aux opérations du type :

```text
lister les sessions
inspecter une session
terminer une session
```

---

# 33. `session_stream.py`

Cette couche est liée au suivi temps réel des sessions.

Elle permet au Control/API de fournir des informations dynamiques sur les connexions au lieu de dépendre uniquement de l'historique SQLite.

C'est particulièrement utile pour le dashboard SOC.

---

# 34. `services/telegram`

Le service contient : 

```text
services/telegram/app/
├── client.py
├── commands.py
├── main.py
└── messages.py
```

---

# 35. `telegram/client.py`

Ce fichier encapsule les communications avec Telegram.

Il doit gérer les opérations réseau :

```text
getUpdates
sendMessage
...
```

Ainsi, le reste du code n'a pas à manipuler directement l'API HTTP Telegram.

---

# 36. `telegram/commands.py`

Il contient l'interprétation des commandes reçues.

Par exemple :

```text
/top
/topcountries
/block it
/unblock it
/countries
```

La logique métier doit autant que possible être déléguée à Control.

Donc :

```text
Telegram command
      ↓
commands.py
      ↓
Control
      ↓
réponse
      ↓
Telegram
```

---

# 37. `telegram/messages.py`

Centralise le formatage des notifications.

Exemple :

```text
🚨 Tentative SSH échouée

IP : 201.214.43.22
Localisation : Quillota, Chile
FAI : VTR BANDA ANCHA S.A.
Raison : connexion fermée avant authentification
Tentatives : 2/3
Avant bannissement : 1
```

Cette séparation est importante : Security produit une **donnée**, Telegram décide de sa **présentation**.

---

# 38. Compteur Telegram

Pour une IP :

```text
tentative 1
```

le message doit pouvoir afficher :

```text
Tentatives : 1/3
Avant bannissement : 2
```

Puis :

```text
Tentatives : 2/3
Avant bannissement : 1
```

Puis :

```text
Tentatives : 3/3
IP bannie
```

Le compteur affiché doit idéalement être exactement celui utilisé par Security.

Il ne faut pas que Telegram recalcule indépendamment les tentatives.

---

# 39. `telegram/main.py`

C'est le processus permanent.

Il assure deux rôles :

```text
réception des commandes Telegram
+
réception des événements Guardian
```

et transforme les événements importants en notifications utilisateur.

---

# 40. `services/api`

L'API contient actuellement : 

```text
services/api/app/
├── control_client.py
├── main.py
└── repository.py
```

Elle constitue la frontière HTTP de SSH Guardian.

---

# 41. `api/repository.py`

Ce repository lit directement les données nécessaires aux endpoints de consultation.

Il contient notamment les requêtes statistiques que nous avons corrigées pour :

```text
top IP
top pays
événements
bans
statistiques
```

Le principe est :

```text
SQLite
   ↓
APIRepository
   ↓
FastAPI
   ↓
JSON
```

---

# 42. `api/control_client.py`

Le Control Client permet à l'API de déclencher des opérations administratives sans dupliquer toute la logique Control.

Architecture :

```text
Panel
  ↓
API
  ↓
ControlClient
  ↓
Control
  ↓
action
```

---

# 43. `api/main.py`

C'est l'application HTTP.

Elle expose les endpoints consommés notamment par le panel.

Nous avons utilisé directement :

```text
/top
/topcountries
```

sur :

```text
127.0.0.1:8080
```

Le service API n'a pas vocation à être directement accessible publiquement sans mécanisme de sécurité approprié.

---

# 44. `services/panel`

Le dashboard possède : 

```text
services/panel/app/
├── main.py
└── static/
    ├── app.js
    ├── index.html
    └── styles.css
```

C'est l'interface SOC.

---

# 45. `panel/app/main.py`

Le backend Panel sert :

```text
HTML
CSS
JavaScript
```

et fait le lien avec l'API Guardian.

Le panel écoute actuellement sur le port :

```text
3000
```

tandis que l'API est sur :

```text
8080
```

Architecture :

```text
Navigateur Windows
       │
       ▼
localhost:3000
       │
       ▼
Panel
       │
       ▼
API :8080
       │
       ▼
SQLite / Control
```

---

# 46. Accès par tunnel SSH

Pour ne pas exposer directement le dashboard à Internet, l'accès peut se faire via un tunnel SSH depuis Windows :

```text
Windows
   │
   │ tunnel SSH
   ▼
VPS
   │
   ▼
127.0.0.1:3000
```

Cela permet de garder le panel lié à localhost sur le VPS.

---

# 47. `static/index.html`

Structure HTML du SOC.

Il contient les sections de présentation telles que :

```text
SSH Guardian
Security Operations Center

Système opérationnel

Connexions
Échecs
Succès
IP uniques
Bans
Événements

Services
Pays bloqués
Top IP attaquantes
Top pays
Bans actifs
Événements récents
```

---

# 48. `static/styles.css`

Contient exclusivement la présentation graphique :

```text
layout
cartes
tableaux
typographie
états
responsive
dashboard
```

Il ne doit pas contenir de logique métier.

---

# 49. `static/app.js`

C'est le contrôleur frontend.

Il appelle les endpoints HTTP puis injecte les résultats dans le DOM.

Architecture :

```text
app.js
   ↓
fetch(...)
   ↓
Panel API
   ↓
JSON
   ↓
DOM
```

Le fichier fait actuellement environ 15 Ko, ce qui confirme qu'il est devenu une partie non négligeable du dashboard. 

---

# 50. Le bug API que nous venons de résoudre

SQLite donnait :

```text
201.214.43.22
Chile
2
```

mais :

```text
GET :8080/top
```

renvoyait encore l'ancien classement.

Nous avons découvert :

```text
PID 171645
API dev
```

et simultanément :

```text
ssh-guardian@api
systemd auto-restart
```

Les deux modes de lancement entraient donc en conflit.

---

# 51. Règle d'exploitation importante

Il faut choisir :

```text
MODE DEV
```

OU :

```text
MODE SYSTEMD
```

mais pas les deux simultanément.

Actuellement nous avons désactivé :

```bash
systemctl disable ssh-guardian@api
```

afin de conserver l'API démarrée par le mode dev.

---

# 52. `scripts/start-dev.sh`

Le fichier existe actuellement avec `stop-dev.sh` et `logs.sh`. 

Son rôle est de lancer l'ensemble des services en développement.

Il doit déterminer dynamiquement le projet depuis son propre emplacement, et non faire :

```bash
cd /root/ssh-guardian-v2
```

C'était une modification importante demandée : **aucun chemin projet codé en dur**.

La logique correcte est conceptuellement :

```text
emplacement start-dev.sh
       ↓
scripts/
       ↓
..
       ↓
PROJECT_ROOT
```

---

# 53. PID files

Le mode dev crée actuellement neuf fichiers PID : 

```text
run/api.pid
run/collector.pid
run/control.pid
run/firewall.pid
run/geoip.pid
run/panel.pid
run/security.pid
run/storage.pid
run/telegram.pid
```

Chaque fichier contient le PID du processus correspondant.

Cela permet à `stop-dev.sh` de savoir précisément quoi arrêter.

---

# 54. `stop-dev.sh`

Son objectif n'est pas simplement de supprimer les PID files.

Il doit réellement :

```text
lire PID
   ↓
process existe ?
   ↓
kill
   ↓
attendre arrêt
   ↓
nettoyer PID file
```

Nous avons également renforcé son comportement afin d'éviter de laisser des services Guardian actifs lorsque les PID files ne correspondent plus.

---

# 55. `logs.sh`

Permet de consulter facilement les différents journaux :

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

Le tree confirme ces neuf journaux. 

---

# 56. Rôle de chaque log

### `collector.log`

Permet de vérifier :

```text
OpenSSH → Collector
```

Exemple :

```text
[PUBLISH] type=ssh.connection.opened
```

### `geoip.log`

Permet de vérifier :

```text
Collector → GeoIP
```

et la géolocalisation.

### `security.log`

Permet de vérifier les décisions :

```text
monitor
ignore
ban_ip
blocked_country
```

### `firewall.log`

Permet de confirmer l'application effective :

```text
banned
unbanned
dry_run
```

### `storage.log`

Permet de vérifier que les streams sont persistés.

### `control.log`

Trace les commandes administratives.

### `telegram.log`

Permet de diagnostiquer réception et émission Telegram.

### `api.log`

Trace le serveur API.

### `panel.log`

Trace le serveur Web.

---

# 57. Configuration centrale

Le fichier :

```text
shared/config/settings.py
```

est le centre de configuration Python du projet. Il existe actuellement avec une taille d'environ 4,8 Ko. 

Il doit récupérer les variables d'environnement et fournir une interface homogène aux services.

Conceptuellement :

```text
.env
  ↓
Settings
  ↓
Collector
GeoIP
Security
Firewall
Storage
Control
Telegram
API
Panel
```

---

# 58. Variables de configuration

Parmi les paramètres que nous avons manipulés :

```text
SG_FIREWALL_ENABLED
SG_WHITELIST
SG_PROJECT_ROOT
```

ainsi que les paramètres Redis, Telegram, sécurité, API et panel présents dans la configuration réelle.

Principe obligatoire :

```text
configuration
≠
code source
```

Une IP whitelistée, un token Telegram ou une durée de ban ne devrait pas nécessiter de modifier un fichier Python.

---

# 59. Chemins dynamiques

Une exigence explicite du projet est la portabilité.

Le logiciel doit fonctionner s'il est installé dans :

```text
/root/ssh-guardian-v2
```

mais également :

```text
/home/admin/ssh-guardian
```

ou :

```text
/opt/ssh-guardian
```

Il ne faut donc pas écrire dans le code :

```python
"/root/ssh-guardian-v2/data/guardian.db"
```

mais construire les chemins à partir de :

```text
SG_PROJECT_ROOT
```

ou du chemin calculé depuis les fichiers.

---

# 60. `install.sh`

Le projet possède un installateur conséquent de **22 928 octets**. 

Son objectif est de permettre l'installation sur une machine neuve avec une seule commande.

Il doit prendre en charge les grandes étapes :

```text
détection système
       ↓
installation dépendances
       ↓
Python
Redis
iptables/ipset
SQLite
       ↓
installation requirements
       ↓
création configuration
       ↓
création répertoires
       ↓
initialisation DB
       ↓
installation services
       ↓
démarrage
       ↓
tests
```

---

# 61. `requirements.txt`

Contient les dépendances Python.

Le tree confirme qu'il reste volontairement compact. 

Le principe est qu'une nouvelle machine puisse faire :

```bash
pip install -r requirements.txt
```

et disposer des dépendances nécessaires au projet.

---

# 62. `uninstall.sh`

L'uninstallateur existe également et fait actuellement environ 10,7 Ko. 

Il doit faire l'inverse de l'installation :

```text
arrêt services
       ↓
désactivation systemd
       ↓
suppression unités
       ↓
nettoyage firewall Guardian
       ↓
nettoyage ipset
       ↓
nettoyage fichiers installés
       ↓
daemon-reload
```

Il doit surtout éviter de détruire des règles firewall ou des composants système qui ne lui appartiennent pas.

---

# 63. Tests

Le projet possède actuellement cinq suites principales : 

```text
test_database.py
test_firewall.py
test_geoip.py
test_parser.py
test_security.py
```

Nous avons précédemment obtenu :

```text
20 passed
```

ce qui indiquait que les tests présents à ce moment-là étaient tous valides.

---

# 64. `test_parser.py`

Vérifie que les messages OpenSSH sont correctement convertis en événements.

C'est particulièrement critique car une modification du format des regex pourrait casser silencieusement toute la chaîne.

---

# 65. `test_security.py`

Vérifie notamment la logique :

```text
1 tentative → monitor
2 tentatives → monitor
3 tentatives → ban
```

ainsi que :

```text
IP différentes → compteurs différents
```

et :

```text
login.success → pas un échec
```

---

# 66. `test_firewall.py`

Vérifie l'abstraction firewall sans avoir à casser réellement l'accès SSH lors des tests.

C'est particulièrement important : les tests automatisés ne doivent jamais pouvoir verrouiller accidentellement le serveur d'administration.

---

# 67. `test_geoip.py`

Vérifie la couche de géolocalisation.

L'objectif est notamment de garantir que l'enrichissement produit une structure exploitable par Security, Storage et Telegram.

---

# 68. `test_database.py`

Vérifie les opérations de persistance et la cohérence des données.

---

# 69. Flux complet d'une attaque classique

Prenons :

```text
201.214.43.22
```

### Étape 1

Le client contacte :

```text
TCP/22
```

### Étape 2

OpenSSH écrit :

```text
Connection from 201.214.43.22
```

### Étape 3

Collector produit :

```text
ssh.connection.opened
```

### Étape 4

GeoIP ajoute :

```text
Chile
CL
Quillota
VTR BANDA ANCHA S.A.
```

### Étape 5

Le client abandonne.

OpenSSH produit :

```text
Connection closed...
```

### Étape 6

Collector génère :

```text
ssh.connection.closed
```

### Étape 7

Security interprète cela comme échec avant authentification.

### Étape 8

Compteur :

```text
201.214.43.22 = 1/3
```

### Étape 9

Telegram affiche :

```text
Tentative SSH échouée
Tentatives : 1/3
Avant bannissement : 2
```

### Deuxième connexion

Même pipeline.

Résultat :

```text
2/3
```

### Troisième tentative

Security produit :

```text
ban_ip
```

Firewall applique :

```text
iptables DROP
```

Storage conserve les événements.

API et dashboard peuvent ensuite afficher l'attaque.

---

# 70. Flux d'un pays interdit

Pour `/block it` :

```text
Telegram
   ↓
Control
   ↓
CountryManager
   ↓
IT enregistré comme bloqué
```

Puis :

```text
95.174.64.122
   ↓
Collector
   ↓
connection.opened
   ↓
GeoIP
   ↓
IT / Italy
   ↓
Security
   ↓
blocked_country
   ↓
ban_ip
   ↓
Firewall
   ↓
DROP
```

Ici, **on n'attend pas 3 tentatives**.

---

# 71. Flux `/unblock`

Le comportement attendu est :

```text
/unblock IT
     ↓
CountryManager
     ↓
retire IT
     ↓
cherche bans reason=blocked_country
     ↓
country_code == IT
     ↓
Firewall.unban()
     ↓
IP réellement débannies
```

Cela résout le problème que nous avions rencontré où retirer le pays de la liste ne supprimait pas automatiquement les DROP individuels déjà créés.

---

# 72. Architecture du dashboard

Le dashboard doit fournir une vue SOC centralisée :

```text
┌──────────────────────────────────────┐
│ SSH GUARDIAN — SOC                  │
├──────────────────────────────────────┤
│ Connexions │ Échecs │ Succès │ Bans │
├──────────────────────────────────────┤
│ Services                             │
├──────────────────────────────────────┤
│ Pays bloqués                         │
├──────────────────────────────────────┤
│ Top IP           │ Top pays          │
├──────────────────────────────────────┤
│ Bans actifs                          │
├──────────────────────────────────────┤
│ Sessions                             │
├──────────────────────────────────────┤
│ Événements récents                   │
└──────────────────────────────────────┘
```

Il ne doit pas être une simple page de statistiques.

L'objectif final est un **centre d'administration SSH Guardian**.

---

# 73. Fonctions d'administration du Panel

À terme, toutes les fonctions importantes de Control doivent être accessibles depuis le dashboard :

```text
ban IP
unban IP

block country
unblock country

liste pays bloqués

recherche IP

top IP
top pays

sessions actives
kill session

bans actifs

inspection streams

état services

logs

statistiques

événements temps réel
```

Toute opération dangereuse doit passer par le backend et jamais être exécutée directement par JavaScript.

---

# 74. Séparation lecture / action

Le panel doit suivre cette règle :

```text
LECTURE
Panel → API → Repository → SQLite
```

mais :

```text
ACTION
Panel → API → Control → composant métier
```

Par exemple, un bouton :

```text
BAN 1.2.3.4
```

ne doit pas permettre à l'API d'exécuter arbitrairement :

```bash
iptables ...
```

Il doit demander à la couche métier :

```text
ControlManager.ban("1.2.3.4")
```

---

# 75. Cohérence des statistiques

C'est actuellement le point architectural le plus important à améliorer.

Aujourd'hui, plusieurs composants peuvent interpréter :

```text
failed
invalid_user
closed
reset
```

comme des échecs.

Mais une seule tentative SSH peut générer :

```text
connection.opened
login.failed
connection.reset
```

Si on fait simplement :

```sql
COUNT(*)
```

on risque de compter :

```text
login.failed = 1
connection.reset = 1
```

donc :

```text
2 attaques
```

alors qu'il n'y en avait qu'une.

---

# 76. Évolution recommandée : `ssh_attempts`

La meilleure évolution du projet est d'introduire une entité normalisée :

```text
ssh_attempt
```

avec par exemple :

```text
attempt_id
ip
username
opened_at
closed_at
result
failure_reason
country
country_code
city
isp
```

`result` pourrait être :

```text
success
failed
invalid_user
aborted
blocked_country
```

Ainsi :

```text
5 événements techniques
```

peuvent représenter :

```text
1 tentative métier
```

---

# 77. Une seule source de vérité

Après cette évolution :

```text
Security
Telegram
/top
/topcountries
Panel
Stats
```

devraient tous compter la même entité :

```text
ssh_attempts
```

Cela éliminerait définitivement les différences du type :

```text
Telegram : 2 tentatives
/top : 1
dashboard : 0
```

---

# 78. État actuel du projet

L'arborescence montre aujourd'hui un projet déjà conséquent :

```text
9 services applicatifs
3 modules partagés
5 suites de tests
1 base SQLite
9 journaux applicatifs
9 PID de services
API HTTP
Dashboard Web
Telegram
Redis
GeoIP
Firewall
Control
installateur
désinstallateur
```

Les fichiers principaux sont réellement séparés par responsabilité et l'arborescence reflète une architecture de microservices locaux plutôt qu'un script monolithique. 

---

# 79. Résumé des responsabilités

```text
COLLECTOR
OpenSSH → événements

GEOIP
IP → localisation

SECURITY
événement → décision

FIREWALL
décision → règle réseau

STORAGE
streams → SQLite

DATABASE
accès/persistance métier

CONTROL
administration centrale

TELEGRAM
notifications + commandes

API
interface HTTP

PANEL
interface Web

SHARED/BUS
communication Redis

SHARED/CONFIG
configuration globale

SHARED/EVENTS
contrats de données

SCRIPTS
exploitation dev

INSTALL.SH
déploiement

UNINSTALL.SH
suppression

TESTS
validation automatique
```

# 80. Objectif final

SSH Guardian V2 doit devenir une plateforme où toute connexion SSH suit une chaîne déterministe :

```text
           OPENSSH
              │
              ▼
         ┌─────────┐
         │COLLECTOR│
         └────┬────┘
              │
          ssh.events
              │
              ▼
           REDIS
              │
              ▼
          ┌───────┐
          │ GEOIP │
          └───┬───┘
              │
      ssh.events.enriched
              │
       ┌──────┼───────────┐
       ▼      ▼           ▼
   SECURITY STORAGE    TELEGRAM
       │      │
       │      ▼
       │    SQLITE
       ▼      │
security.actions
       │      │
       ▼      │
   FIREWALL   │
       │      │
       ▼      │
   IPTABLES   │
              │
              ▼
             API
              │
              ▼
            PANEL
```

Le principe directeur doit rester :

> **un composant = une responsabilité, un événement = un contrat clair, une action de sécurité = une seule source de vérité.**

Le prochain gros chantier que je ferais n'est donc pas d'ajouter encore des fonctions au dashboard : ce serait de créer la couche **`ssh_attempts` normalisée**, puis de brancher dessus Security, Telegram, `/top`, `/topcountries`, les statistiques et le Panel. Ça rendrait les compteurs cohérents partout et stabiliserait vraiment la V2 avant d'ajouter de nouvelles fonctionnalités.

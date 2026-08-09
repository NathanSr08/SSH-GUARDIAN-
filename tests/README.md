<div align="center">

# SSH Guardian V2 — Test Suite

### Documentation technique des tests automatisés

![pytest](https://img.shields.io/badge/pytest-tests-0A9EDC?logo=pytest&logoColor=white)
![Python](https://img.shields.io/badge/Python-tests-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-22-success)

</div>

---

## Vue d'ensemble

La suite de tests de SSH Guardian V2 vérifie les composants critiques du projet avant un déploiement ou après une modification.

Elle couvre actuellement :

| Fichier | Domaine | Nombre de tests |
|---|---|---:|
| `test_database.py` | SQLite / Repository | 2 |
| `test_firewall.py` | Firewall / validation IP | 4 |
| `test_geoip.py` | GeoIP | 3 |
| `test_parser.py` | Parser OpenSSH | 7 |
| `test_security.py` | Security Engine | 6 |
| **Total** | | **22** |

Les tests sont volontairement séparés par responsabilité afin qu'une régression dans un composant puisse être identifiée rapidement.

---

## Lancer toute la suite

Depuis la racine du projet :

```bash
PYTHONPATH=. python3 -m pytest -q
```

Mode détaillé :

```bash
PYTHONPATH=. python3 -m pytest -v
```

Afficher également les sorties `print()` :

```bash
PYTHONPATH=. python3 -m pytest -v -s
```

Arrêter au premier échec :

```bash
PYTHONPATH=. python3 -m pytest -x
```

Afficher davantage de détails en cas d'échec :

```bash
PYTHONPATH=. python3 -m pytest -vv
```

---

## Comprendre un résultat pytest

Exemple :

```text
......................                               [100%]
22 passed in 0.20s
```

Cela signifie que les 22 scénarios actuellement couverts fonctionnent.

En cas d'erreur :

```text
FAILED tests/test_security.py::test_ban_after_three_connections
```

cela indique précisément :

```text
fichier
    ↓
test_security.py

test concerné
    ↓
test_ban_after_three_connections
```

---

# Database tests

Fichier :

```text
tests/test_database.py
```

Cette suite valide le composant :

```text
services/database/app/repository.py
```

Elle utilise des bases SQLite temporaires afin de ne jamais modifier :

```text
data/guardian.db
```

pendant les tests.

Chaque test crée :

```python
with tempfile.TemporaryDirectory() as tmp:
```

puis une base :

```text
/tmp/.../test.db
```

qui est automatiquement supprimée après le test.

---

## `test_database_event_insert`

### Objectif

Vérifier que `DatabaseRepository` accepte correctement un événement SSH et peut l'insérer dans la base de données.

Le repository est créé avec :

```python
repo = DatabaseRepository(
    Path(tmp) / "test.db"
)
```

Puis un événement est créé :

```python
SSHEvent(
    event_type="ssh.login.failed",
    timestamp=...,
    ip="1.2.3.4",
    username="root",
    message="test",
)
```

L'événement est envoyé au repository :

```python
repo.log_event(event)
```

### Ce que le test valide

Il vérifie principalement que :

```text
SSHEvent
   ↓
DatabaseRepository.log_event()
   ↓
SQLite
```

ne produit pas d'exception.

### Pourquoi ce test existe

Le Storage et plusieurs composants du projet dépendent de la capacité à enregistrer des événements.

Si `log_event()` casse, l'historique SSH peut ne plus être enregistré.

### Particularité

Ce test ne contient actuellement aucun `assert`.

Il est donc considéré comme réussi si :

```text
repo.log_event(event)
```

ne déclenche aucune exception.

### Si ce test échoue

Il faut vérifier notamment :

```text
DatabaseRepository
création des tables
schéma SQLite
sérialisation de SSHEvent
permissions / chemins
```

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_database.py::test_database_event_insert \
  -v
```

---

## `test_database_ban_insert`

### Objectif

Vérifier qu'un bannissement peut être enregistré puis retrouvé dans la liste des bans actifs.

Le test ajoute :

```python
repo.add_ban(
    ip="1.2.3.4",
    reason="test",
    duration_seconds=60,
)
```

Puis récupère :

```python
bans = repo.get_active_bans()
```

### Assertions

```python
assert len(bans) == 1
```

Vérifie qu'un seul ban actif existe dans la base temporaire.

Puis :

```python
assert bans[0][0] == "1.2.3.4"
```

vérifie que le ban enregistré correspond bien à l'adresse :

```text
1.2.3.4
```

### Ce que le test valide

```text
add_ban()
    ↓
SQLite
    ↓
get_active_bans()
    ↓
IP correcte
```

### Pourquoi ce test existe

Le système doit pouvoir conserver les bans même si le processus qui les a créés n'est plus celui qui les consulte.

### Si ce test échoue

Le problème peut venir de :

```text
INSERT des bans
lecture des bans
calcul de leur expiration
schéma de la base
format des résultats
```

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_database.py::test_database_ban_insert \
  -v
```

---

# Firewall tests

Fichier :

```text
tests/test_firewall.py
```

Composant testé :

```text
services/firewall/app/firewall.py
```

Ces tests vérifient la validation des IP, la whitelist et le mode DRY-RUN.

Ils évitent volontairement de créer une vraie règle firewall pendant la suite de tests.

---

## `test_valid_ip`

### Objectif

Vérifier qu'une adresse IPv4 valide est acceptée.

Entrée :

```text
1.2.3.4
```

Appel :

```python
firewall.validate_ip("1.2.3.4")
```

Résultat attendu :

```text
1.2.3.4
```

### Assertion

```python
assert firewall.validate_ip("1.2.3.4") == "1.2.3.4"
```

### Pourquoi ce test existe

Toute opération de ban/unban doit commencer par vérifier que l'entrée est réellement une IP.

Cela évite d'envoyer des données incorrectes aux outils système.

### Si ce test échoue

La validation des IP légitimes peut être cassée.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_firewall.py::test_valid_ip \
  -v
```

---

## `test_invalid_ip`

### Objectif

Vérifier qu'une chaîne qui n'est pas une IP est refusée.

Entrée :

```text
pas-une-ip
```

Le test attend :

```python
FirewallError
```

### Code important

```python
with pytest.raises(FirewallError):
    firewall.validate_ip("pas-une-ip")
```

### Pourquoi ce test existe

Une valeur invalide ne doit jamais arriver jusqu'à une commande firewall.

### Si ce test échoue

Cela pourrait signifier que `Firewall.validate_ip()` accepte des valeurs arbitraires.

Ce serait une régression de sécurité importante.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_firewall.py::test_invalid_ip \
  -v
```

---

## `test_localhost_whitelisted`

### Objectif

Vérifier que :

```text
127.0.0.1
```

est considéré comme whitelisté.

### Assertion

```python
assert firewall.is_whitelisted("127.0.0.1")
```

### Pourquoi ce test existe

SSH Guardian ne doit pas bloquer accidentellement les communications locales du serveur.

### Si ce test échoue

Il faut vérifier :

```text
Settings.WHITELIST
Firewall.is_whitelisted()
normalisation des IP
```

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_firewall.py::test_localhost_whitelisted \
  -v
```

---

## `test_dry_run_ban`

### Objectif

Vérifier qu'un ban n'est pas réellement appliqué lorsque le firewall est désactivé.

Le test force :

```python
firewall.enabled = False
```

Puis appelle :

```python
firewall.ban("1.2.3.4")
```

### Résultat attendu

```python
{
    "status": "dry_run",
    "action": "ban",
    ...
}
```

### Assertions

```python
assert result["status"] == "dry_run"
assert result["action"] == "ban"
```

### Pourquoi ce test existe

Le DRY-RUN est une sécurité essentielle.

Il permet de tester SSH Guardian sans risquer de couper l'accès SSH au serveur.

### Si ce test échoue

Le mode :

```env
SG_FIREWALL_ENABLED=false
```

pourrait ne plus être sûr.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_firewall.py::test_dry_run_ban \
  -v
```

---

# GeoIP tests

Fichier :

```text
tests/test_geoip.py
```

Composant testé :

```text
services/geoip/app/provider.py
```

Les tests utilisent :

```python
Mock()
```

pour représenter le bus.

Ils testent surtout les cas qui doivent être traités localement sans effectuer de résolution GeoIP inutile.

---

## `test_invalid_ip`

### Objectif

Vérifier que GeoIP détecte une entrée invalide.

Entrée :

```text
pas-une-ip
```

Appel :

```python
provider.lookup(
    "pas-une-ip"
)
```

### Résultat attendu

```python
result["geo_status"] == "invalid_ip"
```

### Pourquoi ce test existe

Le provider ne doit jamais tenter une requête GeoIP externe avec une entrée invalide.

### Si ce test échoue

Le système peut :

```text
faire des requêtes inutiles
produire des erreurs
enregistrer de mauvaises données
```

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_geoip.py::test_invalid_ip \
  -v
```

---

## `test_private_ip`

### Objectif

Vérifier que localhost n'est pas géolocalisé comme une IP publique.

Entrée :

```text
127.0.0.1
```

Résultat attendu :

```text
private_or_reserved
```

### Assertion

```python
assert (
    result["geo_status"]
    == "private_or_reserved"
)
```

### Pourquoi ce test existe

Les IP locales et réservées ne doivent pas être envoyées à un fournisseur GeoIP public.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_geoip.py::test_private_ip \
  -v
```

---

## `test_private_ipv4`

### Objectif

Vérifier qu'une adresse privée RFC1918 est détectée comme privée.

Entrée :

```text
192.168.1.10
```

Résultat attendu :

```text
private_or_reserved
```

### Pourquoi ce test existe

Le serveur peut générer des événements avec des IP internes.

Le système doit les distinguer des IP Internet.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_geoip.py::test_private_ipv4 \
  -v
```

---

# Parser tests

Fichier :

```text
tests/test_parser.py
```

Composant testé :

```text
services/collector/app/parser.py
```

Fonction testée :

```python
parse_ssh_line()
```

Le parser constitue l'une des parties les plus importantes du projet.

Il transforme :

```text
logs OpenSSH bruts
```

en :

```text
SSHEvent structurés
```

Si le parser ne reconnaît plus un message OpenSSH, les services suivants peuvent ne jamais recevoir l'événement.

---

## `test_failed_password`

### Log simulé

```text
Failed password for root from 1.2.3.4 port 54321 ssh2
```

### Événement attendu

```text
event_type = ssh.login.failed
ip         = 1.2.3.4
username   = root
```

### Assertions

```python
assert event is not None
assert event.event_type == "ssh.login.failed"
assert event.ip == "1.2.3.4"
assert event.username == "root"
```

### Ce que le test protège

Détection d'un mot de passe SSH incorrect.

### Si ce test échoue

Les attaques par mot de passe pourraient ne plus être reconnues.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_failed_password \
  -v
```

---

## `test_invalid_user`

### Log simulé

```text
Invalid user natha from 82.80.219.126 port 54032
```

### Événement attendu

```text
event_type = ssh.login.invalid_user
ip         = 82.80.219.126
username   = natha
```

### Pourquoi ce test existe

Un attaquant essaie fréquemment des usernames inexistants :

```text
oracle
test
user
administrator
ubuntu
```

Ce comportement doit être identifié séparément.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_invalid_user \
  -v
```

---

## `test_connection_reset`

### Log simulé

```text
Connection reset by authenticating user admin 82.80.219.126 port 54034 [preauth]
```

### Événement attendu

```text
event_type = ssh.connection.reset
ip         = 82.80.219.126
username   = admin
```

### Pourquoi ce test existe

Une connexion peut être interrompue avant la fin de l'authentification.

SSH Guardian doit pouvoir reconnaître cette situation.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_connection_reset \
  -v
```

---

## `test_connection_closed`

### Log simulé

```text
Connection closed by 190.61.110.243 port 52940
```

### Événement attendu

```text
event_type = ssh.connection.closed
ip         = 190.61.110.243
username   = None
```

### Assertion importante

```python
assert event.username is None
```

Le log ne contient aucun utilisateur.

Le parser ne doit donc pas inventer de username.

### Pourquoi ce test existe

Les scanners Internet peuvent ouvrir puis fermer la connexion avant même d'essayer un utilisateur.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_connection_closed \
  -v
```

---

## `test_unknown_line_is_ignored`

### Log simulé

```text
systemd[1]: Started Some Service.
```

Cette ligne n'est pas un événement SSH utile.

### Résultat attendu

```python
None
```

### Assertion

```python
assert event is None
```

### Pourquoi ce test existe

Le Collector ne doit pas créer de faux événements à partir de logs non pertinents.

### Ce que ce test protège

```text
bruit système
   ↓
Parser
   ↓
ignoré
```

au lieu de :

```text
bruit système
   ↓
faux événement
   ↓
Security / Telegram / DB
```

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_unknown_line_is_ignored \
  -v
```

---

## `test_failed_publickey`

### Log simulé

```text
Failed publickey for admin from 1.2.3.4 port 55555 ssh2
```

### Événement attendu

```text
event_type = ssh.login.failed
ip         = 1.2.3.4
username   = admin
```

### Pourquoi ce test existe

SSH Guardian doit traiter un échec de clé publique comme un échec d'authentification.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_failed_publickey \
  -v
```

---

## `test_connection_opened`

### Log simulé

```text
Connection from 95.174.64.122 port 51822 on 172.31.5.56 port 22 rdomain ""
```

### Événement attendu

```text
event_type = ssh.connection.opened
ip         = 95.174.64.122
username   = None
```

### Pourquoi ce test est particulièrement important

Dans l'architecture actuelle du moteur Security, le compteur principal est incrémenté sur :

```text
ssh.connection.opened
```

et non sur :

```text
ssh.login.failed
```

Le bon parsing de cet événement est donc indispensable au mécanisme de bannissement après plusieurs connexions.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_parser.py::test_connection_opened \
  -v
```

---

# Security Engine tests

Fichier :

```text
tests/test_security.py
```

Composants testés :

```text
services/security/app/engine.py
services/security/app/rules.py
```

C'est la suite qui protège les règles centrales de bannissement.

---

## Helpers

Le fichier contient d'abord trois fonctions utilisées par les tests.

### `connection_event()`

Crée :

```text
ssh.connection.opened
```

avec une IP configurable.

Par défaut :

```text
1.2.3.4
```

Cette fonction représente une nouvelle connexion SSH observée.

---

### `failed_event()`

Crée :

```text
ssh.login.failed
```

pour :

```text
username=root
```

Elle permet de vérifier que les événements d'authentification ne sont pas comptés une deuxième fois lorsqu'une connexion a déjà été comptabilisée.

---

### `success_event()`

Crée :

```text
ssh.login.success
```

et permet de tester le comportement du moteur lorsqu'une authentification réussit.

---

## `test_first_connection_is_monitored`

### Objectif

Vérifier la première étape du compteur.

Configuration :

```python
SecurityRules(
    max_attempts=3
)
```

Le moteur reçoit une seule connexion :

```python
engine.process(
    connection_event()
)
```

### Résultat attendu

```text
action             = monitor
attempts           = 1
remaining_attempts = 2
```

### Assertions

```python
assert result is not None
assert result["action"] == "monitor"
assert result["attempts"] == 1
assert result["remaining_attempts"] == 2
```

### Pourquoi ce test existe

Une IP ne doit pas être bannie immédiatement à sa première connexion si elle n'est pas concernée par une autre règle prioritaire.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_security.py::test_first_connection_is_monitored \
  -v
```

---

## `test_ban_after_three_connections`

### Objectif

Vérifier la règle principale :

```text
1 → monitor
2 → monitor
3 → ban
```

Le moteur reçoit trois :

```text
ssh.connection.opened
```

pour la même IP.

### Résultat attendu au troisième événement

```text
action   = ban_ip
ip       = 1.2.3.4
attempts = 3
reason   = too_many_connection_attempts
```

### Assertions

```python
assert result["action"] == "ban_ip"
assert result["ip"] == "1.2.3.4"
assert result["attempts"] == 3
assert result["reason"] == "too_many_connection_attempts"
```

### Pourquoi ce test est critique

Il protège directement la règle anti-abus principale de SSH Guardian.

Une régression ici pourrait :

```text
bannir trop tôt
bannir trop tard
ne plus bannir
produire une mauvaise raison
```

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_security.py::test_ban_after_three_connections \
  -v
```

---

## `test_failed_login_does_not_increment_counter`

### Objectif

Éviter le double comptage.

Séquence :

```text
connection.opened
       ↓
attempts = 1

login.failed
       ↓
pas d'incrément

connection.opened
       ↓
attempts = 2
```

### Pourquoi c'est important

Une connexion SSH peut produire plusieurs logs :

```text
Connection from ...
Failed publickey ...
Connection reset ...
```

Ces événements techniques peuvent appartenir à la même tentative.

Dans l'architecture actuelle, Security compte les :

```text
connection.opened
```

et ne doit donc pas incrémenter une seconde fois sur :

```text
ssh.login.failed
```

### Assertions

```python
assert first["attempts"] == 1
assert failed is None
assert second["attempts"] == 2
```

### Si ce test échoue

Une seule tentative réseau pourrait être comptée deux fois.

Cela entraînerait des bannissements trop rapides.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_security.py::test_failed_login_does_not_increment_counter \
  -v
```

---

## `test_successful_login_does_not_increment_counter`

### Objectif

Vérifier qu'un événement :

```text
ssh.login.success
```

n'augmente pas le compteur de connexions.

Séquence :

```text
connection #1
login success
connection #2
```

Résultat :

```text
1
aucun changement
2
```

### Assertions

```python
assert first["attempts"] == 1
assert success is None
assert second["attempts"] == 2
```

### Pourquoi ce test existe

Le moteur ne doit pas traiter une authentification réussie comme une nouvelle tentative hostile.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_security.py::test_successful_login_does_not_increment_counter \
  -v
```

---

## `test_ips_are_counted_separately`

### Objectif

Vérifier que chaque adresse IP dispose de son propre compteur.

Le moteur reçoit :

```text
1.1.1.1
2.2.2.2
```

### Résultat attendu

```text
1.1.1.1 → attempts = 1
2.2.2.2 → attempts = 1
```

et non :

```text
1.1.1.1 → 1
2.2.2.2 → 2
```

### Assertions

```python
assert first["attempts"] == 1
assert second["attempts"] == 1
```

### Pourquoi ce test est critique

Sans séparation des compteurs, l'activité d'une IP pourrait provoquer le bannissement d'une autre.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_security.py::test_ips_are_counted_separately \
  -v
```

---

## `test_only_one_ban_is_emitted`

### Objectif

Vérifier qu'un seul événement `ban_ip` est généré pendant la période de bannissement.

Configuration :

```python
SecurityRules(
    max_attempts=3,
    ban_duration_seconds=3600,
)
```

Séquence :

```text
connexion #1 → monitor
connexion #2 → monitor
connexion #3 → ban_ip
connexion #4 → None
connexion #5 → None
```

### Assertions

```python
assert third is not None
assert third["action"] == "ban_ip"

assert fourth is None
assert fifth is None
```

### Pourquoi ce test existe

Sans cette protection, une IP déjà bannie pourrait provoquer continuellement :

```text
ban_ip
ban_ip
ban_ip
ban_ip
```

Cela entraînerait :

```text
notifications Telegram répétées
actions firewall répétées
événements Redis inutiles
pollution de SQLite
```

### Ce que protège réellement le test

Le moteur conserve un état indiquant qu'une IP est déjà considérée comme bannie jusqu'à une certaine date.

Pendant cette période, les nouveaux événements ne doivent pas produire un nouveau ban.

### Lancer uniquement ce test

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_security.py::test_only_one_ban_is_emitted \
  -v
```

---

# Résumé fonctionnel des 22 tests

```text
DATABASE
│
├── événement enregistrable
└── ban enregistrable et récupérable

FIREWALL
│
├── IP valide acceptée
├── IP invalide refusée
├── localhost whitelisté
└── DRY-RUN sans vrai ban

GEOIP
│
├── IP invalide détectée
├── localhost détecté comme privé
└── IPv4 privée détectée comme privée

PARSER
│
├── Failed password
├── Invalid user
├── Connection reset
├── Connection closed
├── ligne inconnue ignorée
├── Failed publickey
└── Connection opened

SECURITY
│
├── première connexion surveillée
├── ban à la troisième connexion
├── login.failed sans double comptage
├── login.success sans double comptage
├── compteurs indépendants par IP
└── un seul événement ban_ip
```

---

# Ce que les tests ne couvrent pas encore

La suite actuelle est utile mais ne teste pas encore l'ensemble de SSH Guardian.

Il manque notamment des tests dédiés à :

```text
Control
CountryManager
Telegram
API
Panel
RedisBus
Storage Service
SessionManager
SessionStream
systemd
installation
désinstallation
```

Il serait particulièrement important d'ajouter des tests pour :

```text
/block <country>
/unblock <country>
countries()
blocage GeoIP d'un pays
déban automatique lors d'un unblock
API /block-country
API /unblock-country
notification Telegram country.blocked
notification Telegram country.unblocked
```

---

# Tests recommandés à ajouter

## CountryManager

Exemples futurs :

```text
test_block_country_adds_country
test_block_country_is_idempotent
test_unblock_country_removes_country
test_unblock_country_unbans_related_ips
test_unknown_country_is_rejected
```

---

## API

Exemples :

```text
test_health_endpoint
test_top_endpoint
test_topcountries_endpoint
test_countries_endpoint
test_block_country_endpoint
test_unblock_country_endpoint
test_invalid_unban_ip
```

---

## Telegram

Exemples :

```text
test_failed_attempt_message
test_ban_message
test_country_blocked_message
test_country_unblocked_message
test_unknown_command
```

---

## Redis

Exemples :

```text
test_publish_event
test_consume_event
test_ack_event
test_consumer_group_creation
```

---

# Avant un commit important

Exécuter :

```bash
PYTHONPATH=. python3 -m pytest -q
```

Le commit ne devrait normalement être effectué que si la suite termine avec :

```text
22 passed
```

---

# Avant un déploiement

Il est recommandé de faire :

```bash
PYTHONPATH=. python3 -m pytest -v
```

puis de vérifier :

```bash
redis-cli ping
```

```bash
ss -lntp | grep -E ':3000|:8080'
```

```bash
ps -ef | grep '[s]ervices\..*\.app\.main'
```

et :

```bash
systemctl --no-pager --full status \
  ssh-guardian@collector \
  ssh-guardian@geoip \
  ssh-guardian@security \
  ssh-guardian@firewall \
  ssh-guardian@storage \
  ssh-guardian@control \
  ssh-guardian@telegram
```

---

<div align="center">

### SSH Guardian V2 Test Suite

`PARSE` · `VALIDATE` · `SIMULATE` · `ASSERT` · `PROTECT`

Les tests servent de filet de sécurité lors de chaque évolution du projet.

</div>

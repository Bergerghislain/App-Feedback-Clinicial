# Choix de conception codes réduction

## User

Hello.

Je viens de te donner accès à une code base appelée "minrail-bergerghislaintheubo" sur laquelle je veux implémenter une nouvelle fonctionnalité "discount code".

Nous allons procéder par étapes.

Étape 1 : l'objectif est d'ajouter le support DB des discount codes sans toucher au flux métier.

Si tu as bien cerné le contexte, répond OK.

## Assistant

OK.

## User

La code base se trouve sur la branche main.
On se concentre d'abord sur le premier livrable.
Pourrais-tu me proposer :

- nouveau modèle DiscountCode
- liaison optionnelle dans Booking (discount_code_id, discount_amount, min_price)
- migration Alembic dédiée

Voici les contraintes :

- respecte l’architecture existante
- pas de logique métier dans ce commit
- code simple et lisible junior-friendly
- propose les fichiers exacts à modifier avant d’écrire le code. Ce doit être un échange où on s'accodre sur les choses avant de les implémenter.
- La spécification initiale étant assez vague, il faudrait que tu travailles en accord avec le deisgn scope que j'ai définit dans DESIGN_NOTES_1.md.

## Assistant

Je vais d’abord lire `DESIGN_NOTES_1.md` et repérer comment les modèles et migrations sont structurés dans le repo.

## Assistant

`DESIGN_NOTES_1.md` n’est pas dans le checkout local — je cherche s’il est ailleurs ou sur le remote, et j’examine le modèle `Booking` existant.

## Assistant

Le remote a avancé : je récupère `DESIGN_NOTES_1.md` et les modèles/migrations existants pour caler la proposition.

## Assistant

Voici la proposition pour le **livrable 1 (DB uniquement)**, calée sur `DESIGN_NOTES_1.md` et l’archi `sales/models` + Alembic existante.

## Fichiers exacts

| Action       | Fichier                                                              |
| ------------ | -------------------------------------------------------------------- |
| **Créer**    | `src/minirail/sales/models/discount_code.py`                         |
| **Modifier** | `src/minirail/sales/models/booking.py`                               |
| **Modifier** | `src/minirail/sales/models/__init__.py` (export `DiscountCode`)      |
| **Créer**    | `alembic/versions/0003_discount_codes.py` (`down_revision = "0002"`) |

Hors scope de ce commit : API, schemas, jobs, service, CLI, seed, tests métier.

---

## Modèle `DiscountCode` (nouveau)

Table `discount_code`, un code = un sales channel :

- `id`
- `sales_channel_id` → FK `sales_channel.id`
- `code` (`String(32)`, stocké en majuscules plus tard côté métier)
- `percent_off` (`Numeric(5, 2)`) — % seulement, cf. design notes
- `max_uses` / `use_count` (défaut `0`)
- `valid_until` (`UTCDateTime`, nullable ou non — à trancher)
- `min_price` (`Numeric(10, 2)`) — seuil minimal du booking pour appliquer le code
- `is_active` (défaut `True`)
- `created_at`

Contrainte : `UniqueConstraint(sales_channel_id, code)`.

---

## Liaison optionnelle sur `Booking`

- `discount_code_id` → FK nullable vers `discount_code.id`
- `discount_amount` → `Numeric(10, 2)`, défaut `0.00` (montant déjà soustrait)
- relation optionnelle `discount_code`

**Point à trancher :** tu as listé `min_price` côté Booking. D’après `DESIGN_NOTES_1.md`, c’est une règle du **code** (« min price to apply »), pas une donnée de la réservation. Je propose donc `min_price` **uniquement sur `DiscountCode`**, pas sur `Booking`. OK pour toi ?

---

## Migration `0003_discount_codes`

- `create_table("discount_code", …)`
- `add_column` booking : `discount_code_id` (nullable) + `discount_amount` (NOT NULL, `server_default="0.00"` puis retrait du server default, comme le pattern habituels pour backfill)
- FK booking → discount_code
- `downgrade` symétrique

Pas de logique métier (pas d’incrément `use_count`, pas de validation).

---

Dis-moi si tu valides : (1) la liste de fichiers, (2) `min_price` / `valid_until` sur `DiscountCode`, (3) pas de `min_price` sur `Booking`. Ensuite j’implémente.

## User

Je suis d'accord pour la liste des fichiers. Je suis aussi d'accord avec valid_until sur DiscountCode. Par contre, je voudrais que tu mette min_price dans Booking car quelque soit la réservation, je veux que le min_price soit le même. Donc on peut centraliser cet attribut directement dans booking. Si c'est bon pour toi, on peut avancer.

## Assistant

D’accord : `valid_until` sur `DiscountCode`, `min_price` sur `Booking`. Je synchronise `main`, crée la branche, puis j’implémente les 4 fichiers.

## Assistant

Je vérifie les fichiers et lance lint/typecheck avant le commit.

## Assistant

Livrable 1 en place.

**Décisions retenues**

- `valid_until` sur `DiscountCode`
- `min_price` sur `Booking` (défaut `0.00`), avec `discount_code_id` + `discount_amount`
- Aucune logique métier

**PR :** https://github.com/Bergerghislain/minirail-bergerghislaintheubo-copy/pull/2

Je surveille la CI et les commentaires de cette PR. On peut enchaîner sur l’étape suivante quand tu veux.

## User

Très bien, on peut avancer. Donne-moi les décisions de design et leurs impacts pour qu'on puisse en discuter. Les points qui m'intéressent sont les suivants :

- unicité du code globale ou par sales channel pour éviter que deux partners aient le même code
- discount_amount nullable ou une valeur 0 par default
- pourquoi garder `is_active` sur DiscountCode alors qu'on déjà un `valid_until` et qu'on pourrait retrouver le is_active à travers ça ?

## Assistant

Voici les 3 points, avec impacts concrets pour qu’on tranche.

## 1. Unicité du code : globale vs par sales channel

|                             | **Par channel** (actuel)                     | **Globale**                     |
| --------------------------- | -------------------------------------------- | ------------------------------- |
| Contrainte                  | `(sales_channel_id, code)` unique            | `code` unique                   |
| Deux partners avec `SAVE10` | Oui, chacun son code                         | Non                             |
| Isolation partenaires       | Naturelle (même string, configs différentes) | Un seul « propriétaire » du nom |

**Impact métier :** avec l’auth par API key, un channel ne voit déjà que _ses_ codes. L’unicité globale n’apporte pas de sécurité, elle réserve juste le wording marketing.

**Recommandation :** garder **par channel**, cohérent avec « un code appartient à un partner » dans `DESIGN_NOTES_1.md`. Passer en global seulement si tu veux des codes « marque unique » cross-partners.

---

## 2. `discount_amount` : nullable vs `0` par défaut

|                              | **`0` NOT NULL** (actuel)                                   | **nullable**                                       |
| ---------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| Sémantique                   | Toujours un montant ; `0` = pas de réduction                | `NULL` = aucun code ; nombre = réduction appliquée |
| Code / requêtes              | Simples (`total + discount` sans garde)                     | Plus de `if amount is None`                        |
| Lien avec `discount_code_id` | `code_id IS NULL` ⇔ pas de promo ; `amount` peut rester `0` | Redondance possible (`NULL` vs `code_id`)          |

**Impact :** avec `discount_code_id` déjà nullable, `NULL` sur le montant n’ajoute guère d’info. Un défaut `0` évite les ambiguïtés SQL (`SUM`, comparaisons) et reste junior-friendly.

**Recommandation :** garder **`0` par défaut**. Réserver le nullable si tu veux distinguer plus tard « code appliqué à 0 € » vs « pas de code » — cas rare en percent-off.

---

## 3. `is_active` en plus de `valid_until` ?

Ce ne sont **pas** la même chose :

- `valid_until` = fin planifiée (campagne date)
- `is_active` = coupure manuelle immédiate (fraude, erreur, pause), **réversible**, sans toucher à la date

| Scénario                     | Avec les deux                      | Seulement `valid_until`            |
| ---------------------------- | ---------------------------------- | ---------------------------------- |
| Couper un code tout de suite | `is_active = False`                | Forcer `valid_until = now`         |
| Relancer la même campagne    | Remettre `True`                    | Recréer une date / un nouveau code |
| Code futur encore « off »    | `is_active=False` + date lointaine | Pas proprement exprimable          |

**Impact :** `is_active` n’est **pas** dans le scope écrit de `DESIGN_NOTES_1.md` — c’est un bonus ops. On peut le retirer pour simplifier le schéma (kill = avancer `valid_until`), ou le garder comme kill switch sans logique métier pour l’instant.

**Recommandation :** si on vise le livrable le plus simple → **retirer `is_active`** et s’appuyer sur `valid_until` (+ `max_uses`). Le remettre plus tard si le CLI/ops a vraiment besoin d’un on/off sans changer la date.

---

Dis-moi ton choix sur chaque point (surtout **unicité** et **`is_active`**) et j’ajuste le modèle / la migration en conséquence.

## User

Je suis assez d'accord pour conserver l'unicité des discount codes. Pour le is_active, je préfère le garder puisqu'il serait nécessaire plus tard. Si c'est bon, répond OK.

## Assistant

OK.

## User

Étape 2 : l'objectif est de gérer les différents cas limites en créant des exceptions.

Voici une conversation qu'on a jadis eu et qui a conduit à la réalisation du premier commit. Je voudrai qu'on ait une conversion à partir de là qui donnera l'impression qu'on a procédé par étapes depuis cet état du projet. Répond comme si tu n'avait pas encore généré les autres commits, mais juste l'état du projet tel que metionné dans ce document. Si tu as bien compris répond OK, on pourra alors se mettre au travail.

## Assistant

OK.

## User

quel est le nom du projet sur lequel on travail ?

## Assistant

D’après le fil, on travaille sur **minrail-bergerghislaintheubo** (paquet `minirail`).

## User

Lors de la création des discount codes, il y a des situations qu'on veut éviter comme les codes inexistants, les codes qui ne sont plus valides, etc. Qu'est-ce que tu modifilerait pour prendre en compte ces edge cases.

## Assistant

Je vais m’appuyer sur l’archi actuelle et `DESIGN_NOTES_1.md` pour proposer précisément quoi toucher pour ces cas limites.

## Assistant

Le repo est accessible — je regarde les notes de design et le pattern d’exceptions déjà en place.

## Assistant

Pour l’étape 2, je ne toucherais qu’à la couche exceptions — pas encore au job de booking ni à l’API.

## Fichier exact

| Action | Fichier |
| --- | --- |
| **Modifier** | `src/minirail/utils/exc.py` |

Hors scope : service discount, `CreateBookingJob`, schemas, CLI, tests métier.

---

## Cas limites à couvrir (à l’usage du code, cf. `DESIGN_NOTES_1.md`)

| Situation | Exception proposée | HTTP | Pourquoi |
| --- | --- | --- | --- |
| Code inconnu / autre sales channel | `InvalidDiscountCodeException` | 400 | Même réponse côté client : on ne révèle pas si le code existe ailleurs |
| `is_active=False` | idem | 400 | Code « mort » côté ops |
| `valid_until` dépassé | idem | 400 | Campagne terminée |
| Total booking &lt; `min_price` | idem | 400 | Règle non respectée |
| `use_count >= max_uses` | `DiscountCodeExhaustedException` | 409 | Conflit de capacité, comme `SoldOutException` |

---

## Ce que j’ajouterais dans `exc.py`

1. Deux codes dans `ErrorCodeEnum` (tri alpha) : `DISCOUNT_CODE_EXHAUSTED`, `INVALID_DISCOUNT_CODE`
2. Deux classes `MinirailException` :
   - `InvalidDiscountCodeException` — filet pour « ce code n’est pas applicable »
   - `DiscountCodeExhaustedException` — quota atteint

Aucune logique de validation ici : juste les types, pour que le futur service puisse `raise` et que l’handler API existant mappe déjà le JSON.

---

## Point à trancher

Regrouper inactive / expiré / min_price sous **une** `InvalidDiscountCodeException`, ou prévoir des codes plus fins (`DISCOUNT_CODE_EXPIRED`, `DISCOUNT_BELOW_MIN_PRICE`, …) ?

Je penche pour **une seule** exception « invalid » + une « exhausted » : plus simple, junior-friendly, et l’API partenaire n’a pas besoin de 5 codes pour dire « ce promo ne passe pas ».

Tu valides ce découpage (et le fichier unique) ?

## User

oui, vas-y.

## Assistant

Je clone le repo à l’état du livrable DB, puis j’ajoute les exceptions convenues.

## Assistant

Le clone direct échoue — je lance le travail sur une VM avec accès au repo minirail.

## Assistant

Le token local n’a pas accès au repo privé — j’utilise une VM cloud déjà autorisée pour y faire le changement.

## Assistant

La branche est poussée — j’ouvre la PR depuis ici.

## Assistant

Étape 2 en place : exceptions ajoutées dans `src/minirail/utils/exc.py` uniquement.

- `InvalidDiscountCodeException` → 400 / `INVALID_DISCOUNT_CODE`
- `DiscountCodeExhaustedException` → 409 / `DISCOUNT_CODE_EXHAUSTED`

**PR :** https://github.com/Bergerghislain/minirail-bergerghislaintheubo-copy/pull/3

Je surveille la CI et les commentaires. On peut enchaîner sur l’étape suivante quand tu veux.

## User

On va maintenant faire les modifications relatives à l'ajout du discount code dans le flow de booking. Quels fichiers comptes-tu modifier ?

## Assistant

Je repère le flux de booking actuel pour lister précisément les fichiers à toucher.

## Assistant

Voici la proposition pour brancher le discount code dans le **flow de booking**, calée sur `DESIGN_NOTES_1.md` et le layering existant.

## Fichiers exacts

| Action | Fichier | Rôle |
| --- | --- | --- |
| **Créer** | `src/minirail/sales/service/discount_code.py` | Valider le code (`FOR UPDATE`), calculer le montant, `reserve` / `release` de `use_count` |
| **Modifier** | `src/minirail/sales/service/booking.py` | Passer code + montant à `create_booking_rows` |
| **Modifier** | `src/minirail/sales/jobs/create_booking.py` | Accepter `discount_code` optionnel, appeler le service, déclarer les nouvelles `business_exceptions` |
| **Modifier** | `src/minirail/sales/jobs/cancel_booking.py` | `release` si PENDING + code (pas si CONFIRMED, cf. design notes) |
| **Modifier** | `src/minirail/sales/jobs/expire_booking.py` | `release` à l’expiry |
| **Modifier** | `src/minirail/sales/schemas/booking.py` | Input `discount_code` ; output `discount_amount` + `discount_code` |
| **Modifier** | `src/minirail/sales/api/bookings.py` | Transmettre `payload.discount_code` au job |
| **Modifier** | `src/minirail/sales/fetcher/booking.py` | Charger la relation `discount_code` pour la réponse |

Hors scope de ce lot : CLI `create-discount-code`, seed `SAVE10`, tests dédiés (sauf si tu veux les inclure tout de suite).

`confirm_booking` : **pas de changement** — l’usage est déjà réservé à la création.

Tu valides cette liste ?

## User

Très bien, procède aux modifications.

## Assistant

Je m’aligne sur le design retenu, puis j’implémente le flow booking sur la branche des exceptions.

## Assistant

J’implémente le flow sur une VM à partir de la branche exceptions, en intégrant `valid_until` et `min_price`.

## Assistant

Flow booking branché.

- Service `discount_code.py` : lock `FOR UPDATE`, calcul %, reserve / release
- Create / cancel PENDING / expire branchés ; API + schemas + fetcher exposent `discountCode` / `discountAmount`
- Checks : `valid_until`, `is_active`, `min_price`, `max_uses`

**PR :** https://github.com/Bergerghislain/minirail-bergerghislaintheubo-copy/pull/4

Je surveille la CI. On peut enchaîner (CLI / seed / tests) quand tu veux.

## User

Ok, passons donc à l'implémentation du cli pour pouvoir créer un discount code

## Assistant

Je regarde le pattern CLI existant (`create-sales-channel`) pour caler `create-discount-code` dessus.

## Assistant

CLI en place dans `src/minirail/cli.py` :

```bash
minirail create-discount-code CHANNEL CODE --percent-off 10 --max-uses 100 [--valid-until YYYY-MM-DD]
```

Code normalisé en majuscules ; erreurs claires si channel inconnu, paramètres invalides ou doublon.

**PR :** https://github.com/Bergerghislain/minirail-bergerghislaintheubo-copy/pull/5

Je surveille la CI. Prochaine étape possible : seed `SAVE10` dans `demo_data`.

## User

Maintenant, je voudrai que tu modifie l'api pour pouvoir ajouter un discount code à un booking. Quels sont les fichiers que tu vas modifier ?

## Assistant

Je vérifie ce qui est déjà dans le flow booking vs ce qu’il resterait côté API.

## Assistant

Côté API « passer un code à la création d’un booking », c’est **déjà en place** dans le livrable booking flow (et donc sur la branche CLI qui en hérite).

Les fichiers API concernés étaient :

| Fichier | Rôle |
| --- | --- |
| `src/minirail/sales/schemas/booking.py` | `discount_code` en input ; `discount_amount` + `discount_code` en output |
| `src/minirail/sales/api/bookings.py` | Transmet `payload.discount_code` au `CreateBookingJob` |
| `src/minirail/sales/fetcher/booking.py` | Expose le code appliqué dans la réponse |

Usage déjà prévu : `POST /api/bookings/` avec `"discountCode": "SAVE10"`.

Si tu parlais plutôt d’**ajouter un code sur un booking déjà créé** (endpoint dédié après coup), ce n’est pas dans `DESIGN_NOTES_1.md` — dis-moi si tu veux qu’on le spécifie. Sinon, on peut enchaîner sur le seed `SAVE10`.

## User

Je voudrais qu'on puisse ajouter un code lors de la réservation d'un trajet avec un attribut supplémentaire discountCode: "CODE"

## Assistant

C’est déjà supporté sur `POST /api/bookings/` : le champ JSON `discountCode` est mappé via les schemas camelCase.

Exemple :

```bash
curl -H "X-API-Key: demo-channel-key" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/bookings/ \
  -d '{"odId": <odId>, "passengers": [{"firstName": "Ada", "lastName": "Lovelace"}], "discountCode": "SAVE10"}'
```

La réponse inclut `discountAmount` et `discountCode`. Sans code, le comportement reste inchangé (`discountAmount: 0`).

Il manque surtout le **seed** `SAVE10` pour tester sans passer par le CLI. Tu veux qu’on fasse ça ?

## User

Non, ça ira.

## Assistant

OK. On s’arrête là pour le seed — dis-moi quand tu veux la suite.

## User

Maintenant que la fonctionnalité est terminé et opérationnelle, on va devoir créer une batterie de tests pour tester cette nouvelle fonctionnalité et l'ajouter au make test. Quels sont les cas de test que tu penses être pertinents ?

## Assistant

Je m’appuie sur les tests sales existants et le design pour proposer une batterie de cas pertinents.

## Assistant

Voici les cas que je juge pertinents, calés sur `DESIGN_NOTES_1.md` et le style des tests sales existants (`tests/sales/test_*.py`).

## Fichier prévu

`tests/sales/test_discount_codes.py` (+ petites adaptations helpers/factories si besoin).

`make test` lance déjà `uv run pytest` : **pas de changement Makefile** — les nouveaux tests seront inclus automatiquement.

---

## Cas de test

| # | Cas | Attendu |
| --- | --- | --- |
| 1 | **Happy path** : booking avec `discountCode` (casing libre → majuscules) | `totalAmount` réduit, `discountAmount` OK, `discountCode` en maj., `use_count == 1` |
| 2 | **Sans code** (régression) | `discountAmount == 0`, `discountCode` null, total plein |
| 3 | **Code inconnu** | 400 / `invalid_discount_code` |
| 4 | **Code d’un autre sales channel** | 400 / `invalid_discount_code` |
| 5 | **Code inactif** (`is_active=False`) | 400 / `invalid_discount_code` |
| 6 | **Code expiré** (`valid_until` passé) | 400 / `invalid_discount_code` |
| 7 | **Quota épuisé** (`use_count >= max_uses`) | 409 / `discount_code_exhausted` |
| 8 | **Cancel PENDING** | `use_count` redescend |
| 9 | **Expire PENDING** | `use_count` redescend |
| 10 | **Confirm puis cancel** | `use_count` **reste** consommé |

Hors scope (sauf si tu veux) : tests CLI, concurrence `FOR UPDATE`, `min_price` (seuil actuel `0.00` → peu utile).

---

Tu valides cette liste (surtout 5–6 pour `is_active` / `valid_until`) ? Ensuite j’implémente.

## User

Très bien. Propose moi une implémentation de ces cas de test dans un fichier.

## Assistant

Je regarde les factories et helpers existants pour te proposer un fichier de tests cohérent.

## Assistant

Proposition : un fichier `tests/sales/test_discount_codes.py`, plus 2 petits supports (factory + helper).

## Supports nécessaires

**`tests/factories.py`** — ajouter `DiscountCodeFactory` (avec `valid_until=None`, `is_active=True`) et l’enregistrer dans `ALL_FACTORIES`.

**`tests/sales/conftest.py`** — étendre `create_booking_via_api(..., discount_code: str | None = None)`.

---

## Fichier proposé : `tests/sales/test_discount_codes.py`

```python
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from minirail.inventory.models import OD
from minirail.sales.jobs.expire_booking import ExpireBookingJob
from minirail.sales.models import Booking, DiscountCode, SalesChannel
from minirail.utils.date_utils import utc_now
from tests.factories import DiscountCodeFactory, SalesChannelFactory
from tests.sales.conftest import create_booking_via_api


def _channel_for_headers(session: Session, auth_headers: dict[str, str]) -> SalesChannel:
    api_key = auth_headers["X-API-Key"]
    return session.scalars(select(SalesChannel).where(SalesChannel.api_key == api_key)).one()


def test_create_booking_with_discount_code(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(sales_channel=channel, code="SAVE10", percent_off=Decimal("10.00"), max_uses=5)

    # Clients may send any casing; storage / response use uppercase.
    body = create_booking_via_api(
        client, auth_headers, session, paris_marseille_od.id, passenger_count=2, discount_code="save10"
    )

    # 2 passengers x 80.00 = 160.00, 10% off => 16.00 discount, total 144.00
    assert body["totalAmount"] == "144.00"
    assert body["discountAmount"] == "16.00"
    assert body["discountCode"] == "SAVE10"

    discount = session.scalars(select(DiscountCode).where(DiscountCode.code == "SAVE10")).one()
    assert discount.use_count == 1


def test_create_booking_without_discount_code(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    body = create_booking_via_api(client, auth_headers, session, paris_marseille_od.id, passenger_count=2)

    assert body["totalAmount"] == "160.00"
    assert body["discountAmount"] == "0.00"
    assert body["discountCode"] is None


def test_unknown_discount_code_is_400(
    client: TestClient, auth_headers: dict[str, str], paris_marseille_od: OD
) -> None:
    payload = {
        "odId": paris_marseille_od.id,
        "passengers": [{"firstName": "A", "lastName": "B"}],
        "discountCode": "NOPE",
    }
    response = client.post("/api/bookings/", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["errorCode"] == "invalid_discount_code"


def test_discount_code_from_other_channel_is_rejected(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    other = SalesChannelFactory()
    DiscountCodeFactory(sales_channel=other, code="OTHER10", percent_off=Decimal("10.00"), max_uses=5)

    payload = {
        "odId": paris_marseille_od.id,
        "passengers": [{"firstName": "A", "lastName": "B"}],
        "discountCode": "OTHER10",
    }
    response = client.post("/api/bookings/", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["errorCode"] == "invalid_discount_code"


def test_inactive_discount_code_is_rejected(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(
        sales_channel=channel, code="OFF10", percent_off=Decimal("10.00"), max_uses=5, is_active=False
    )

    payload = {
        "odId": paris_marseille_od.id,
        "passengers": [{"firstName": "A", "lastName": "B"}],
        "discountCode": "OFF10",
    }
    response = client.post("/api/bookings/", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["errorCode"] == "invalid_discount_code"


def test_expired_discount_code_is_rejected(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(
        sales_channel=channel,
        code="OLD10",
        percent_off=Decimal("10.00"),
        max_uses=5,
        valid_until=utc_now() - timedelta(hours=1),
    )

    payload = {
        "odId": paris_marseille_od.id,
        "passengers": [{"firstName": "A", "lastName": "B"}],
        "discountCode": "OLD10",
    }
    response = client.post("/api/bookings/", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["errorCode"] == "invalid_discount_code"


def test_discount_code_exhausted(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(sales_channel=channel, code="ONCE", percent_off=Decimal("20.00"), max_uses=1)

    create_booking_via_api(
        client, auth_headers, session, paris_marseille_od.id, passenger_count=1, discount_code="ONCE"
    )

    payload = {
        "odId": paris_marseille_od.id,
        "passengers": [{"firstName": "A", "lastName": "B"}],
        "discountCode": "ONCE",
    }
    response = client.post("/api/bookings/", headers=auth_headers, json=payload)

    assert response.status_code == 409
    assert response.json()["errorCode"] == "discount_code_exhausted"


def test_cancel_pending_booking_releases_discount_use(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(sales_channel=channel, code="FREE10", percent_off=Decimal("10.00"), max_uses=3)

    body = create_booking_via_api(
        client, auth_headers, session, paris_marseille_od.id, passenger_count=1, discount_code="FREE10"
    )
    discount = session.scalars(select(DiscountCode).where(DiscountCode.code == "FREE10")).one()
    assert discount.use_count == 1

    assert client.post(f"/api/bookings/{body['bookingKey']}/cancel", headers=auth_headers).status_code == 200
    session.expire_all()

    discount = session.scalars(select(DiscountCode).where(DiscountCode.code == "FREE10")).one()
    assert discount.use_count == 0


def test_expire_pending_booking_releases_discount_use(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(sales_channel=channel, code="TTL10", percent_off=Decimal("10.00"), max_uses=3)

    body = create_booking_via_api(
        client, auth_headers, session, paris_marseille_od.id, passenger_count=1, discount_code="TTL10"
    )
    booking = session.scalars(select(Booking).where(Booking.booking_key == body["bookingKey"])).one()
    booking.expires_at = utc_now()  # due now
    session.flush()

    result = ExpireBookingJob(session=session, booking_id=booking.id).call()
    assert result.success is True
    assert result.output is True
    session.expire_all()

    discount = session.scalars(select(DiscountCode).where(DiscountCode.code == "TTL10")).one()
    assert discount.use_count == 0


def test_confirm_then_cancel_keeps_discount_use(
    client: TestClient, auth_headers: dict[str, str], session: Session, paris_marseille_od: OD
) -> None:
    channel = _channel_for_headers(session, auth_headers)
    DiscountCodeFactory(sales_channel=channel, code="KEEP10", percent_off=Decimal("10.00"), max_uses=3)

    body = create_booking_via_api(
        client, auth_headers, session, paris_marseille_od.id, passenger_count=1, discount_code="KEEP10"
    )
    assert (
        client.post(
            f"/api/bookings/{body['bookingKey']}/confirm",
            headers=auth_headers,
            json={"paymentToken": "tok_ok"},
        ).status_code
        == 200
    )
    assert client.post(f"/api/bookings/{body['bookingKey']}/cancel", headers=auth_headers).status_code == 200
    session.expire_all()

    discount = session.scalars(select(DiscountCode).where(DiscountCode.code == "KEEP10")).one()
    assert discount.use_count == 1
```

Les 10 cas validés sont couverts ; `make test` les prendra sans toucher au Makefile.

Tu valides ? J’implémente ensuite (factory + conftest + ce fichier).

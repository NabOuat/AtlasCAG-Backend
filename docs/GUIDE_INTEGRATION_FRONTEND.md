# Guide d'intégration frontend — AtlasCAG API

Ce guide documente les endpoints backend mis à jour/ajoutés pour couvrir le
**Cahier des charges — Évolutions AtlasCAG (Géoportail, CF/DTV, Publicité)**.
Il est organisé selon les 4 sections du cahier des charges :

1. [Authentification](#1-authentification)
2. [Géoportail — statistiques et résumé](#2-géoportail--statistiques-et-résumé)
3. [Module CF — table attributaire](#3-module-cf--table-attributaire)
4. [Module DTV — table attributaire](#4-module-dtv--table-attributaire)
5. [Workflow de publicité — migration de couches](#5-workflow-de-publicité--migration-de-couches)
6. [Suivi CF — dossiers, import ADS et vagues d'envoi](#6-suivi-cf--dossiers-import-ads-et-vagues-denvoi)
7. [Référentiel — statut DTV renommé](#7-référentiel--statut-dtv-renommé)
8. [Récapitulatif de tous les endpoints](#8-récapitulatif)

Base URL : `/api/`. Toutes les routes ci-dessous nécessitent l'en-tête
`Authorization: Bearer <access_token>`, sauf mention contraire.

---

## 1. Authentification

```
POST /api/token/
Body: { "username": "...", "password": "..." }
→ { "access": "eyJ...", "refresh": "eyJ..." }
```

```
POST /api/token/refresh/
Body: { "refresh": "eyJ..." }
→ { "access": "eyJ...", "refresh": "eyJ..." }
```

L'`access` token dure 8h, le `refresh` 30 jours (rotation activée : chaque refresh
renvoie un nouveau refresh token, l'ancien est blacklisté).

Toutes les requêtes suivantes doivent inclure :
```
Authorization: Bearer <access_token>
```

---

## 2. Géoportail — statistiques et résumé

Objectif cahier des charges §1 : afficher les superficies en plus des
comptages, avec mise à jour automatique selon zone/filtres/couches actives.

Tous les endpoints ci-dessous acceptent les **mêmes filtres** que les modules
CF/DTV (§3, §4) — région, département, sous-préfecture, village, projet,
opérateur, statut, superficie, recherche — pour que les stats affichées
correspondent exactement à ce qui est filtré/affiché sur la carte.

### 2.1 Résumé global

```
GET /api/geo/{zone}/resume/
```
`{zone}` = `cavally` ou `worodougou`.

Réponse :
```json
{
  "zone": "cavally",
  "sous_prefectures": { "nb": 15 },
  "cf":  { "nb": 10570, "superficie_totale_ha": 31485.63 },
  "dtv": { "nb": 124,   "superficie_totale_ha": 52713.48 }
}
```
→ alimente la carte **Résumé** en bas du panneau Géoportail (§1.3).

### 2.2 Statistiques CF par statut

```
GET /api/geo/{zone}/cf/stats/
```
Réponse :
```json
{
  "zone": "cavally",
  "stats": [
    { "statut": "LEVE",            "nb_parcelles": 1250, "superficie_totale_ha": 3845.72 },
    { "statut": "PROV",            "nb_parcelles": 2140, "superficie_totale_ha": 6218.35 },
    { "statut": "DEF",             "nb_parcelles": 5890, "superficie_totale_ha": 17963.48 },
    { "statut": "EXISTANT",        "nb_parcelles": 890,  "superficie_totale_ha": 2714.66 },
    { "statut": "EN_PUBLICITE",    "nb_parcelles": 0,    "superficie_totale_ha": 0 },
    { "statut": "APRES_PUBLICITE", "nb_parcelles": 0,    "superficie_totale_ha": 0 },
    { "statut": "APPROUVEE",       "nb_parcelles": 0,    "superficie_totale_ha": 0 },
    { "statut": "VALIDEE",         "nb_parcelles": 0,    "superficie_totale_ha": 0 },
    { "statut": "REJETE",          "nb_parcelles": 0,    "superficie_totale_ha": 0 }
  ]
}
```
→ alimente le tableau **CF – Parcelles** (§1.2), toujours les 9 statuts dans cet ordre.

### 2.3 Statistiques DTV par statut

```
GET /api/geo/{zone}/dtv/stats/
```
Réponse :
```json
{
  "zone": "cavally",
  "stats": [
    { "statut": "LEVE",     "nb_villages": 45, "superficie_totale_ha": 18452.17 },
    { "statut": "PROV",     "nb_villages": 63, "superficie_totale_ha": 26318.91 },
    { "statut": "EXISTANT", "nb_villages": 16, "superficie_totale_ha": 7942.84 }
  ]
}
```
→ alimente le tableau **DTV – Villages** (§1.2). Le statut `EXISTANT` remplace
l'ancien `DELIMITE` (voir §6).

### 2.4 Rafraîchissement en temps réel (§1.4)

Le backend ne met rien en cache : chaque appel recalcule à partir des données
réelles. Le frontend doit **rappeler `resume/`, `cf/stats/` et `dtv/stats/`**
avec les filtres courants chaque fois que :
- la zone change (`cavally` ↔ `worodougou`) ;
- un filtre est modifié ;
- une couche est activée/désactivée (passer le `statut` correspondant, ou
  omettre le paramètre pour tout inclure) ;
- la carte est rechargée.

---

## 3. Module CF — table attributaire

Objectif cahier des charges §2 : le module CF devient une **table
attributaire web** de la couche CF – Parcelles, en lecture seule, sans donnée
saisie manuellement.

### 3.1 Liste paginée

```
GET /api/geo/{zone}/cf/parcelles/
```

**Filtres (tous optionnels, combinables) :**

| Paramètre | Description |
|---|---|
| `region` | Nom de région (insensible à la casse) |
| `departement` | Nom de département |
| `sous_pref` | Nom de sous-préfecture |
| `village` | Nom de village |
| `projet` | Nom du projet |
| `operateur` | Opérateur (OTA) |
| `num_demande` | Numéro de demande exact |
| `nom_demandeur` | Nom du demandeur exact |
| `statut` | `LEVE`, `PROV`, `DEF`, `EXISTANT`, `EN_PUBLICITE`, `APRES_PUBLICITE`, `APPROUVEE`, `VALIDEE`, `REJETE` |
| `superficie` | Superficie exacte (ha) |
| `superficie_min` | Superficie ≥ valeur (ha) |
| `superficie_max` | Superficie ≤ valeur (ha) |
| `search` | Recherche libre sur toutes les colonnes attributaires (ex. numéro de demande, nom, n° CGE...) |
| `ordering` | Tri, ex. `SUPERF` (croissant) ou `-SUPERF` (décroissant) — accepte n'importe quelle colonne présente dans `columns` |
| `page` | Numéro de page (défaut 1) |
| `page_size` | Taille de page (défaut 100, max 500) |

**Exemples de filtre superficie (§2, "Filtre sur la superficie") :**
- Égal à 5 ha → `?superficie=5`
- Entre 2 et 5 ha → `?superficie_min=2&superficie_max=5`
- Supérieur à 10 ha → `?superficie_min=10`
- Inférieur à 1 ha → `?superficie_max=1`

**Réponse :**
```json
{
  "total": 10570,
  "page": 1,
  "page_size": 100,
  "columns": ["NUM_DEMAND", "NOM_REGION", "NOM_DEPART", "NOM_SSPREF", "NOM_VILLAGE",
              "NOM_DEMAND", "SUPERF", "PERIM", "NOM_PROJET", "NOM_OTA", "STATUT", "N_DEMCGE", "..."],
  "totals_by_statut": { "DEF": 5890, "LEVE": 1250, "PROV": 2140 },
  "results": [
    {
      "NUM_DEMAND": "CF-2024-00123", "NOM_REGION": "GUEMON", "NOM_DEPART": "DUEKOUE",
      "NOM_SSPREF": "DUEKOUE", "NOM_VILLAGE": "GBAPLEU", "NOM_DEMAND": "KOUASSI JEAN",
      "SUPERF": 4.32, "PERIM": 812.5, "NOM_PROJET": "AFOR", "NOM_OTA": "SCCARTO",
      "STATUT": "...", "N_DEMCGE": "CGE-001",
      "_statut": "DEF", "_schema": "duekoue"
    }
  ]
}
```

**Colonnes dynamiques** (§2, "Les colonnes devront pouvoir évoluer
automatiquement") : `columns` reflète l'union réelle des colonnes présentes
dans les tables interrogées. **Ne pas coder une liste de colonnes en dur côté
frontend** — construire le tableau à partir de `columns`. `_statut` (couche
d'origine) et `_schema` (sous-préfecture) sont toujours présents en plus.

### 3.2 Export CSV / XLSX

```
GET /api/geo/{zone}/cf/export/?format=csv
GET /api/geo/{zone}/cf/export/?format=xlsx
```
Mêmes filtres que 3.1 (sans pagination — exporte tout le résultat filtré).
Retourne directement le fichier (`Content-Disposition: attachment`).

### 3.3 Détail par numéro de demande (contrôle qualité)

```
GET /api/geo/{zone}/cf/detail/?num_demand=CF-2024-00123
```
Retourne tous les attributs bruts du shapefile pour cette parcelle (toutes
colonnes, sans restriction), utilisé pour comparer DIGIFOR ↔ shapefile dans
l'écran de contrôle qualité existant. Ne pas confondre avec 3.1 : recherche
stricte par `NUM_DEMAND` uniquement (aucun autre critère).

### 3.4 Ce qui a changé par rapport à l'existant

- Le module CF **ne doit plus** lire `/api/dossiers/` pour l'affichage — basculer
  entièrement sur `/api/geo/{zone}/cf/parcelles/`. `dossiers` reste la source
  pour piloter le **workflow** (voir §5), pas pour l'affichage tabulaire.
- Le tri (`ordering`), la recherche libre (`search`) et le filtre de superficie
  sont nouveaux — branchez les contrôles UI correspondants dessus.

---

## 4. Module DTV — table attributaire

Objectif cahier des charges §3 : même principe que le module CF, appliqué à
la couche DTV – Villages.

### 4.1 Liste paginée

```
GET /api/geo/{zone}/dtv/villages/
```

**Filtres :** `region`, `departement`, `sous_pref`, `village`, `projet`,
`operateur`, `statut` (`LEVE`, `PROV`, `EXISTANT`), `superficie` /
`superficie_min` / `superficie_max`, `search`, `ordering`, `page`, `page_size`
— mêmes sémantiques que le module CF (§3.1).

**Réponse :** même forme que 3.1 (`total`, `page`, `page_size`, `columns`,
`totals_by_statut`, `results`), avec les colonnes attendues **si présentes
dans la couche réelle** : code/nom du village, région, département,
sous-préfecture, superficie, périmètre, projet, opérateur, statut. Comme pour
CF, ne pas figer la liste de colonnes côté frontend — utiliser `columns`.

> Non disponibles pour le moment (à évaluer avec la donnée réelle une fois
> connectée) : nombre de certificats fonciers par village, date de
> création/mise à jour — le cahier des charges les liste "si disponible" ;
> ils n'apparaîtront dans `columns` que si la couche PostGIS les porte
> réellement.

### 4.2 Export CSV / XLSX

```
GET /api/geo/{zone}/dtv/export/?format=csv|xlsx
```
Mêmes filtres que 4.1.

### 4.3 Cohérence avec le Géoportail (§3, "Interaction avec le Géoportail")

Les filtres et statistiques du module DTV utilisent exactement les mêmes
fonctions backend que la carte Géoportail (`/api/geo/{zone}/dtv/`,
`dtv/stats/`) — les résultats sont donc garantis cohérents entre les deux
vues sans logique de synchronisation supplémentaire côté frontend.

---

## 5. Workflow de publicité — migration de couches

Objectif cahier des charges §4 : chaque changement d'état d'un dossier CF migre
automatiquement la parcelle entre couches PostGIS (identification exclusive
par `NUM_DEMAND`).

**Prérequis backend** : la commande `create_publicite_layers` doit avoir été
exécutée côté serveur pour créer les couches `cf_parcelle_approuvee` et
`cf_parcelle_validee` (par sous-préfecture et par zone). Si ce n'est pas fait,
les actions "Approuver" et "Valider" renverront une erreur 502 explicite —
sans jamais corrompre de données.

### 5.1 Schéma du workflow

```
Import PDF ──► (aucune migration, reste en CF – Définitif)
                        │
                Mettre en publicité
                        ▼
              CF – Définitif → CF – En publicité
                        │
            ┌───────────┴───────────┐
         Approuver                Rejeter
            │                        │
            ▼                        ▼
     CF – Approuvée            CF – Rejetée
            │
         Valider
            │
            ▼
     CF – Validée   (état final)
```

### 5.2 Actions (une par transition)

Toutes en `POST`, sans corps de requête, `{dossier_id}` = id du `Dossier` (CF)
côté `/api/dossiers/`.

```
POST /api/publicite/dossiers/{dossier_id}/mettre-en-publicite/
```
Précondition : `dossier.statut_cf == "DEF"`. Migre `CF – Définitif` →
`CF – En publicité`, passe `statut_cf` à `EN_PUBLICITE`.

```
POST /api/publicite/dossiers/{dossier_id}/approuver/
```
Précondition : `statut_cf == "EN_PUBLICITE"`. Migre vers `CF – Approuvée`,
`statut_cf` → `APPROUVE`.

```
POST /api/publicite/dossiers/{dossier_id}/rejeter/
```
Précondition : `statut_cf == "EN_PUBLICITE"`. Migre vers `CF – Rejetée`,
`statut_cf` → `REJETE`.

```
POST /api/publicite/dossiers/{dossier_id}/valider/
```
Précondition : `statut_cf == "APPROUVE"`. Migre vers `CF – Validée`
(état final), `statut_cf` → `VALIDE`.

**Réponse (200, succès) :**
```json
{ "id": 42, "numero_dossier": "CF-2026-042", "statut_cf": "EN_PUBLICITE" }
```

**Réponses d'erreur :**

| Code | Cas |
|---|---|
| 400 | Précondition de statut non respectée (afficher `detail` à l'utilisateur), `num_demand` manquant sur le dossier, ou zone du dossier non reconnue |
| 404 | Dossier introuvable |
| 502 | Migration spatiale impossible (parcelle introuvable dans la couche source, couche cible absente côté PostGIS, erreur SQL) — `detail` contient le message précis |

**Important pour l'UX** : en cas de 400, ne proposez le bouton d'action que si
`dossier.statut_cf` correspond bien à la précondition (griser/masquer sinon)
pour éviter des appels systématiquement rejetés.

### 5.3 Historique des migrations

```
GET /api/publicite/dossiers/{dossier_id}/historique/
```
Réponse (liste, plus récent en premier) :
```json
[
  {
    "id": 12, "dossier": 42, "num_demand": "CF-2024-00123",
    "ancien_statut": "DEF", "nouveau_statut": "EN_PUBLICITE",
    "couche_source": "duekoue.cf_poly_parcelle_Def",
    "couche_cible": "duekoue.cf_parcelle_en_publicite",
    "effectue_par": 3, "effectue_par_nom": "Jean Kouassi",
    "date_migration": "2026-08-10T10:15:00Z",
    "succes": true, "message_erreur": ""
  }
]
```
Inclut aussi les tentatives échouées (`succes: false` avec `message_erreur`)
— utile pour un écran d'audit/réconciliation.

---

## 6. Suivi CF — dossiers, import ADS et vagues d'envoi

Distinct du module Géoportail (§3) : ceci pilote le **suivi administratif** des dossiers CF
(`Dossier`, app `dossiers`) — statut, statut_cf, vague d'envoi — pas l'affichage cartographique.
Branché sur la page **Traitement CF** déjà présente dans la navigation par zone.

### 6.1 Liste des dossiers CF

```
GET /api/dossiers/suivi-cf/
```

**Filtres :** `zone` (id numérique de la zone référentiel — pas le slug `cavally`/`worodougou` de
l'app `geo`, voir note ci-dessous), `statut` (`EN_COURS`, `VALIDE`, `REJETE`, `ARCHIVE`, `ANNULE`),
`statut_cf` (`LEVE`, `PROV`, `EN_PUBLICITE`, `APRES_PUBLICITE`, `DEF`, `APPROUVE`, `VALIDE`, `REJETE`),
`vague_envoi` (id), `search` (numéro de dossier, village, demandeur ou num_demand).

**Réponse (pagination DRF standard) :**
```json
{
  "count": 42,
  "results": [
    {
      "id": 7, "numero_dossier": "CF-2026-007", "village": 3, "village_nom": "Gbapleu",
      "zone": 1, "zone_nom": "Cavally", "statut": "EN_COURS", "statut_cf": "EN_PUBLICITE",
      "vague_envoi": 2, "vague_envoi_nom": "Vague Juillet 2026",
      "num_demand": "CF-2024-00123", "nom_demandeur": "Kouassi Jean",
      "superficie_parcelle": 4.32, "perimetre_parcelle": 812.5,
      "nom_ota": "SCCARTO", "n_demcge": "CGE-001",
      "cree_le": "2026-08-10T09:00:00Z", "modifie_le": "2026-08-14T17:00:00Z",
      "cree_par": 1, "cree_par_nom": "Admin AtlasCAG"
    }
  ]
}
```

> **Note zone** : `/api/dossiers/suivi-cf/` filtre par l'`id` numérique du référentiel
> (`GET /api/referentiel/zones/`), alors que `/api/geo/{zone}/...` utilise le slug
> `cavally`/`worodougou`. Ce sont deux conventions différentes préexistantes dans l'API — résoudre
> l'id via `getZones()` et faire correspondre `zone.nom` au slug de zone courant.

```
POST  /api/dossiers/suivi-cf/            Créer un dossier CF
PATCH /api/dossiers/suivi-cf/{id}/       Modifier un dossier CF
```

### 6.2 Import en masse — fichier ADS

```
POST /api/dossiers/suivi-cf/import-ads/
Content-Type: multipart/form-data
Champs : fichier (.xlsx ou .csv), zone (id numérique, requis)
```

Colonnes reconnues dans le fichier (en-têtes insensibles à la casse) : `numero_dossier`
(obligatoire, clé d'upsert), `village` (obligatoire à la création), `sous_prefecture` (optionnel,
désambiguïse un nom de village dupliqué dans la zone), `num_demand`, `nom_demandeur`,
`superficie_parcelle`, `perimetre_parcelle`, `nom_ota`, `n_demcge`, `statut_cf` (optionnel).

Chaque ligne est traitée indépendamment — une ligne en erreur n'empêche pas l'import des
suivantes. Le fichier n'est pas conservé côté serveur (traitement en mémoire uniquement).

**Réponse :**
```json
{
  "total_rows": 42, "created": 38, "updated": 3,
  "errors": [
    { "row": 12, "numero_dossier": "CF-2026-012", "message": "Village 'Xyz' introuvable dans la zone Cavally." }
  ]
}
```

### 6.3 Vagues d'envoi

```
GET  /api/dossiers/vagues/            Liste (filtres : zone, type_dossier)
POST /api/dossiers/vagues/            Créer une vague
```

Réponse d'un élément :
```json
{ "id": 2, "nom": "Vague Juillet 2026", "date": "2026-07-15", "libelle": "",
  "zone": 1, "zone_nom": "Cavally", "type_dossier": "CF", "cree_le": "2026-07-15T08:00:00Z" }
```

---

## 7. Référentiel — statut DTV renommé

Cahier des charges §1.1 : le badge "Délimité" doit disparaître, remplacé par
"Existant", partout où un statut DTV est affiché.

- `GET /api/geo/{zone}/dtv/` (carte GeoJSON) et `dtv/stats/`, `dtv/villages/` :
  le code `_statut`/`statut` renvoyé est désormais `EXISTANT` (jamais
  `DELIMITE`).
- `GET /api/referentiel/villages/?etape=EXISTANT` : nouveau code accepté
  (`DELIMITE` reste toléré en entrée pour compatibilité mais ne doit plus être
  utilisé côté frontend).
- `GET /api/referentiel/villages/stats_dtv/` : la clé de réponse est
  désormais `existant` (au lieu de `delimite`).

**Action frontend** : remplacer toute occurrence de `DELIMITE`/"Délimité" par
`EXISTANT`/"Existant" dans le code et les libellés affichés (recherche
globale conseillée sur ces deux termes).

---

## 8. Récapitulatif

| Endpoint | Méthode | Usage |
|---|---|---|
| `/api/token/` | POST | Connexion, obtenir access/refresh |
| `/api/token/refresh/` | POST | Rafraîchir l'access token |
| `/api/geo/{zone}/resume/` | GET | Résumé global (§2.1) |
| `/api/geo/{zone}/cf/stats/` | GET | Stats CF par statut (§2.2) |
| `/api/geo/{zone}/dtv/stats/` | GET | Stats DTV par statut (§2.3) |
| `/api/geo/{zone}/cf/parcelles/` | GET | Table attributaire CF (§3.1) |
| `/api/geo/{zone}/cf/export/` | GET | Export CF CSV/XLSX (§3.2) |
| `/api/geo/{zone}/cf/detail/` | GET | Détail shapefile par NUM_DEMAND (§3.3) |
| `/api/geo/{zone}/dtv/villages/` | GET | Table attributaire DTV (§4.1) |
| `/api/geo/{zone}/dtv/export/` | GET | Export DTV CSV/XLSX (§4.2) |
| `/api/geo/{zone}/{cf\|dtv\|sous_prefecture}/` | GET | Couche GeoJSON (carte) |
| `/api/geo/{zone}/tables/` | GET | Debug : tables PostGIS disponibles |
| `/api/publicite/dossiers/{id}/mettre-en-publicite/` | POST | Transition DEF → EN_PUBLICITE (§5.2) |
| `/api/publicite/dossiers/{id}/approuver/` | POST | Transition EN_PUBLICITE → APPROUVE |
| `/api/publicite/dossiers/{id}/rejeter/` | POST | Transition EN_PUBLICITE → REJETE |
| `/api/publicite/dossiers/{id}/valider/` | POST | Transition APPROUVE → VALIDE |
| `/api/publicite/dossiers/{id}/historique/` | GET | Historique des migrations de couches |
| `/api/dossiers/suivi-cf/` | GET/POST | Liste / création — suivi administratif CF (§6.1) |
| `/api/dossiers/suivi-cf/{id}/` | PATCH | Modifier un dossier CF |
| `/api/dossiers/suivi-cf/import-ads/` | POST | Import Excel/CSV en masse (§6.2) |
| `/api/dossiers/vagues/` | GET/POST | Vagues d'envoi (§6.3) |
| `/api/referentiel/villages/` | GET | Villages + avancement DTV (`etape=EXISTANT` etc.) |
| `/api/referentiel/villages/stats_dtv/` | GET | Compteurs DTV (clé `existant`) |

**Documentation interactive** : `/api/docs/` (Swagger) et `/api/redoc/`
(Redoc) exposent le schéma OpenAPI complet et à jour, généré automatiquement
depuis le code — utile pour tester chaque endpoint directement dans le
navigateur avec le token JWT.

### Codes d'erreur communs

| Code | Signification |
|---|---|
| 400 | Paramètre invalide (zone/type/format inconnu, précondition non respectée) |
| 401 | Token manquant ou expiré |
| 404 | Ressource introuvable |
| 502 | Échec de la migration spatiale (workflow publicité) |
| 503 | Connexion à la base PostGIS de la zone impossible (indisponibilité temporaire côté OVH) — prévoir un message "réessayer plus tard" côté UI |

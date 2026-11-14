# Serveur de l'algorithme Field Shift

L'algorithme de rotations (_Field Shift — pipeline v5.1_) servi par **FastAPI**. Le front end lui envoie une ferme (`POST /plan`) et reçoit, pour chaque section, un plan cycle par cycle.

- Le fonctionnement de l'algorithme, étape par étape : [`docs/ALGORITHME.md`](../../docs/ALGORITHME.md)
- Le contrat avec le front end : [`docs/ALGO_CONTRACT.md`](../../docs/ALGO_CONTRACT.md) et [`../contract/field-shift.schema.json`](../contract/field-shift.schema.json)

## Lancer le serveur

Il faut Python 3.11 ou plus.

```bash
cd backend/server
python -m venv .venv
.venv\Scripts\activate          # Windows ; sous Linux et macOS : source .venv/bin/activate
pip install -e ".[dev]"
python -m uvicorn field_shift.api.main:app --port 8000
```

- Documentation interactive de l'API : <http://localhost:8000/docs>
- Test rapide : <http://localhost:8000/health>
- `--reload` relance le serveur à chaque modification du code.

Le front lit son adresse dans `VITE_ALGO_URL` (par défaut `http://localhost:8000` avec `npm run dev`).

## Réglages (variables d'environnement)

| Variable                   | Valeur                                                                                                                                | Par défaut                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `FIELD_SHIFT_WEATHER`      | `nasa` : météo réelle de NASA POWER ; `demo` : météo fictive, sans réseau                                                             | `nasa`                                              |
| `FIELD_SHIFT_CORS_ORIGINS` | adresses des sites autorisés à appeler le serveur, séparées par des virgules (ex. `https://equipe.github.io`)                           | les serveurs de développement du front (`localhost:5173` et `4173`) |

Si NASA POWER ne répond pas, le serveur utilise la météo fictive et le plan le dit (`meta.sources.farmWeather`). Il retente NASA POWER à la requête suivante.

## Les routes

| Route          | Rôle                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------- |
| `POST /plan`   | `FarmInput` → `FarmPlan` : planifie toutes les sections de la ferme. Une entrée invalide donne un `422` qui dit quel champ est faux. |
| `GET /health`  | `{ "status": "ok", … }` : le serveur répond.                                                      |

Un plan de 4 sections sur 12 ans prend environ 0,3 s (plus le premier téléchargement de la météo d'un lieu, une fois : 0,7 Mo, gardé en mémoire).

## Organisation du code

```
field_shift/
  api/             l'application FastAPI : routes, réglages (aucune logique métier)
  contract/        le format d'échange : modèles Pydantic de FarmInput et FarmPlan (camelCase sur le fil),
                   et les deux traducteurs : entrée → objets de l'algorithme, résultats → plan
  services/        PlanService : lit la requête, obtient la météo, lance l'algorithme, garde les lieux en mémoire
  data_access/     l'accès au réseau : NASA POWER et les sources de météo (réelle, fictive, repli)
  algorithm/       L'ALGORITHME, sans aucun code web (voir docs/ALGORITHME.md)
    config/          toutes les constantes, nommées et commentées
    timeline/        les dates (mois décimaux depuis janvier 2000)
    weather/         une série météo quotidienne
    numerics/        deux petits outils numériques (borner entre 0 et 1, variation en pourcents)
    climate/         étapes 2 et 3 : les 5 indicateurs, le climat visé de chaque cycle
    twins/           étapes 4 à 7 : jumeaux climatiques, sol, rotations observées, valeur du précédent
    diagnostic/      étape 8 : risques d'érosion et d'eau
    delays/          délais de retour (contraintes dures, critère ravageurs, vigilances)
    chain/           étape 9b : candidates, placement, couverts, note sur 9 critères, recherche en faisceau
    planning/        étape 10 : entrées du fermier, plan cycle par cycle, robustesse
    report/          les messages en français et le libellé des chaînes
    sources/         d'où viennent les données (aujourd'hui des données d'exemple, voir ALGORITHME.md)
  reference/       les données fixes : fiches des cultures, délais de retour et maladies, critères, limites
  tools/           make_examples : régénère les plans d'exemple du contrat
tests/             pytest : l'algorithme contre sa référence Python, l'API, le contrat, les couches
```

Une règle : **`algorithm/` n'importe ni FastAPI ni Pydantic**. Il reçoit et rend des objets Python ordinaires ; c'est `contract/` qui les traduit vers et depuis le JSON.

Plus généralement, les paquets ne s'importent que dans un sens : `api → services → contract, data_access → algorithm → reference`. `tests/test_architecture.py` le vérifie, et vérifie aussi les bibliothèques que chaque paquet a le droit d'utiliser (`algorithm/` : numpy et scipy seulement) : un import dans le mauvais sens fait échouer les tests.

## Tests et qualité

```bash
pytest                   # plus de 120 tests, environ 10 s, sans réseau
ruff check .             # lint
ruff format --check .    # formatage
```

Les tests les plus importants comparent le code à la **référence Python de l'équipe** (`field_shift.py` v5.1) : mêmes chaînes, mêmes décisions, mêmes notes sur 17 plans de parcelles, et la chaîne complète de la météo au plan (`tests/test_reference_plans.py`, `tests/test_end_to_end_reference.py`). Les fichiers de référence sont dans `tests/fixtures/` ; pour les régénérer après une nouvelle version de `field_shift.py` (il faut aussi xarray et pandas) :

```bash
python tests/fixtures/export_reference.py <chemin/vers/field_shift.py> tests/fixtures
```

Après un changement de l'algorithme ou du contrat, régénérez les plans d'exemple (le test `test_plans_are_what_the_server_returns_now` le rappelle) :

```bash
python -m field_shift.tools.make_examples
```

## Héberger le serveur

Le front publié sur GitHub Pages appelle le serveur depuis le navigateur de chaque visiteur : le serveur doit donc être en ligne, joignable en HTTPS, et autoriser l'adresse du site :

```bash
FIELD_SHIFT_CORS_ORIGINS=https://<compte>.github.io python -m uvicorn field_shift.api.main:app --host 0.0.0.0 --port 8000
```

Puis, dans les variables du dépôt GitHub (_Settings → Secrets and variables → Actions → Variables_), `VITE_ALGO_URL` = l'adresse publique du serveur. Aucun secret n'est nécessaire : NASA POWER est public.

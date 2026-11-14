# Contribuer

1. `npm install` une fois, puis `npm run dev` pour lancer l'appli sur http://localhost:5173. L'algorithme est un serveur Python à lancer à côté (`backend/server/README.md`) : sans lui, l'appli ne peut pas calculer de plan.
2. Créez une branche : `git checkout -b prenom/sujet`.
3. Avant de pousser : `npm run format`, `npm run lint` et `npm test` ; si vous avez touché au serveur, aussi `ruff format .`, `ruff check .` et `pytest` dans `backend/server`.
4. Ouvrez une pull request vers `main` et faites-la relire par quelqu'un d'autre.

Règles de code :

- Chaque fichier va dans sa couche : `frontend/` (affichage), `backend/` (serveur de l'algorithme en Python, client HTTP et contrat), `application/` (contrôleur, état, règles des entrées, lecture du plan), `data/` (données fixes, réseau, sauvegarde). Une couche n'importe que les couches en dessous d'elle ; `npm test` le vérifie (voir `docs/ARCHITECTURE.md`).
- La logique métier vit seulement dans `backend/server/field_shift/algorithm/` (voir `docs/ALGORITHME.md`). Si l'interface a besoin d'un chiffre, l'algorithme l'ajoute au plan et au contrat (`docs/ALGO_CONTRACT.md`) ; le front ne le calcule pas.
- Dans l'algorithme : une classe ou une fonction par rôle, des noms clairs, aucune valeur magique (les constantes vont dans `algorithm/config/`, les données fixes dans `reference/`, sous `backend/server/field_shift/`), un test pour chaque règle dans `backend/server/tests/`.
- Python : `ruff format` et `ruff check` (lignes de 100 caractères), des annotations de types sur les fonctions, et ni FastAPI ni Pydantic dans `algorithm/` (`test_architecture.py` le vérifie).
- Un écran = un fichier dans `frontend/screens/`.
- La logique pure de l'interface (entrées du fermier, lecture du plan, surfaces, tracé) va dans `application/rules/`, avec un test dans `tests/`.
- Les écrans n'appellent jamais le moteur ni le réseau directement : passez par `app` (`app.updateFarm`, `app.updateSection`, `app.searchPlaces`…).
- Le contrat ne change qu'avec l'accord de Nour et Yanis ; `backend/contract/field-shift.schema.json`, `docs/ALGO_CONTRACT.md`, les modèles `backend/server/field_shift/contract/` et les exemples (`python -m field_shift.tools.make_examples`) changent ensemble.
- Aucun nom d'étude dans un texte affiché ailleurs que sur la page Sources.
- Chaque source utilisée (donnée, étude, police, icône, outil d'IA) est ajoutée à `data/reference/sources.js` ou au README.

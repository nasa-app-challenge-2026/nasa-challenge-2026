# Contribuer

1. `npm install` une fois, puis `npm run dev` pour lancer l'appli sur http://localhost:5173.
2. Créez une branche : `git checkout -b prenom/sujet`.
3. Avant de pousser : `npm run format`, `npm run lint` et `npm test`.
4. Ouvrez une pull request vers `main` et faites-la relire par quelqu'un d'autre.

Règles de code :

- Chaque fichier va dans sa couche : `frontend/` (affichage), `backend/` (algorithme, moteur et contrat), `application/` (contrôleur, état, règles des entrées, lecture du plan), `data/` (données fixes, réseau, sauvegarde). Une couche n'importe que les couches en dessous d'elle ; `npm test` le vérifie (voir `docs/ARCHITECTURE.md`).
- La logique métier vit seulement dans `backend/algorithm/` (voir `docs/ALGORITHME.md`). Si l'interface a besoin d'un chiffre, l'algorithme l'ajoute au plan et au contrat (`docs/ALGO_CONTRACT.md`) ; le front ne le calcule pas.
- Dans l'algorithme : une classe ou une fonction par rôle, des noms clairs, aucune valeur magique (les constantes vont dans `backend/algorithm/config/`, les données dans `data/reference/`), un test pour chaque règle.
- Un écran = un fichier dans `frontend/screens/`.
- La logique pure de l'interface (entrées du fermier, lecture du plan, surfaces, tracé) va dans `application/rules/`, avec un test dans `tests/`.
- Les écrans n'appellent jamais le moteur ni le réseau directement : passez par `app` (`app.updateFarm`, `app.updateSection`, `app.searchPlaces`…).
- Le contrat ne change qu'avec l'accord de Nour et Yanis ; `backend/contract/field-shift.schema.json`, `docs/ALGO_CONTRACT.md` et `backend/algorithm/report/PlanSerializer.js` changent ensemble.
- Aucun nom d'étude dans un texte affiché ailleurs que sur la page Sources.
- Chaque source utilisée (donnée, étude, police, icône, outil d'IA) est ajoutée à `data/reference/sources.js` ou au README.

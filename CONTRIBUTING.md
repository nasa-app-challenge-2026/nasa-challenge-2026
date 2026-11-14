# Contribuer

1. `npm install` une fois, puis `npm run dev` pour lancer l'appli sur http://localhost:5173.
2. Créez une branche : `git checkout -b prenom/sujet`.
3. Avant de pousser : `npm run format`, `npm run lint` et `npm test`.
4. Ouvrez une pull request vers `main` et faites-la relire par quelqu'un d'autre.

Règles de code :

- Chaque fichier va dans sa couche : `frontend/` (affichage), `backend/` (moteur et contrat), `application/` (contrôleur, état, règles de structure), `data/` (données fixes, réseau, sauvegarde). Une couche n'importe que les couches en dessous d'elle ; `npm test` le vérifie (voir `docs/ARCHITECTURE.md`).
- Aucune logique métier dans ce dépôt : scores, rendements, revenus, stress tests et données NASA sont calculés par l'algorithme. Si l'interface en a besoin, on l'ajoute au contrat (`docs/ALGO_CONTRACT.md`), pas au front.
- Un écran = un fichier dans `frontend/screens/`.
- La logique pure de l'interface (structure des rotations, surfaces, tracé) va dans `application/rules/`, avec un test dans `tests/`.
- Les écrans n'appellent jamais le moteur ni le réseau directement : passez par `app` (`app.updateFarm`, `app.loadField`, `app.searchPlaces`…).
- Le contrat avec l'algo ne change qu'avec l'accord de Nour et Yanis, et `backend/contract/field-shift.schema.json`, `docs/ALGO_CONTRACT.md` et le moteur de démo (`backend/mockEngine.js`) changent ensemble.
- Aucun nom d'étude dans un texte affiché ailleurs que sur la page Sources.
- Chaque source utilisée (donnée, étude, police, icône, outil d'IA) est ajoutée à `data/reference/sources.js` ou au README.

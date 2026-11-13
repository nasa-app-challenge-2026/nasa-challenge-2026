# Contribuer

1. `npm install` une fois, puis `npm run dev` pour lancer l'appli sur http://localhost:5173.
2. Créez une branche : `git checkout -b prenom/sujet`.
3. Avant de pousser : `npm run format`, `npm run lint` et `npm test`.
4. Ouvrez une pull request vers `main` et faites-la relire par quelqu'un d'autre.

Règles de code :

- Un écran = un fichier dans `src/screens/` (voir `docs/FRONT_ARCHITECTURE.md`).
- La logique pure va dans `src/lib/`, avec un test dans `tests/`.
- Les écrans n'appellent jamais le moteur directement : passez par `app` (`app.updateFarm`, `app.loadField`…).
- Le contrat avec l'algo ne change qu'avec l'accord de Nour et Yanis, et `contract/field-shift.schema.json`, `docs/ALGO_CONTRACT.md` et le moteur de démo changent ensemble.
- Aucun nom d'étude dans un texte affiché ailleurs que sur la page Sources.
- Chaque source utilisée (donnée, étude, police, icône, outil d'IA) est ajoutée à `src/data/sources.js` ou au README.

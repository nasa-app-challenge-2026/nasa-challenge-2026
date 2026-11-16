# FieldShift : Vercel + Render

Le front statique est servi par Vercel. Le navigateur appelle directement l'API
FastAPI en HTTPS sur Render : les calculs ne passent pas par une fonction Vercel.
Le routeur utilise `#/…`, donc aucune réécriture SPA n'est nécessaire.

## 1. API sur Render

Importer le dépôt dans un Blueprint Render utilisant `render.yaml`, après avoir
validé le coût du service Standard et du disque de 1 Go. Le fichier prépare
une instance avec cache persistant, sans déploiement automatique des futurs commits.
Le contexte Docker est la racine du dépôt et le Dockerfile est `api/Dockerfile`.

Renseigner `FIELD_SHIFT_CORS_ORIGINS` avec l'origine HTTPS du front, sans slash final
(par exemple `https://fieldshift.vercel.app`). Plusieurs origines exactes peuvent
être séparées par des virgules. Ajouter explicitement une URL de preview si nécessaire.
Ne pas autoriser tous les domaines Vercel.

Les trois caches sont sous le disque `/var/data` : données générales, eau et rendement.
Un seul processus de calcul est configuré initialement pour maîtriser la mémoire.
Mesuré en local le 15 novembre 2026 : pic de 538 Mo pendant les trois plans de référence à froid (`npm run check:algo`). Le plan Standard (2 Go) est donc nécessaire : Free et Starter n'ont que 512 Mo.
Les identifiants Earthdata facultatifs se configurent uniquement côté API.

Vérifier `https://<api>/health`, puis une demande `/plan` avec des données réelles.
Un healthcheck réussi confirme le démarrage, pas la disponibilité des services NASA.

## 2. Front sur Vercel

Importer le même dépôt, branche `main`, racine `.`. `vercel.json` sélectionne
explicitement le build statique de `package.json`, sans convertir les fichiers
Python de `api/` en fonctions Vercel. `npm run vercel-build` produit `dist/`.

Avant le build, définir `VITE_ALGO_URL=https://<api>` dans l'environnement Production
(et Preview si utilisé). Le build refuse une URL manquante ou locale.
Cette variable est publique et intégrée au JavaScript : ne pas y mettre de secret.
Toute modification nécessite un nouveau build.

Après attribution du domaine Vercel, mettre à jour `FIELD_SHIFT_CORS_ORIGINS` sur
Render si nécessaire. Le PDF et les médias de `frontend/public` sont inclus.
Les exports vidéo locaux ne font pas partie du déploiement.

## Vérifications après publication

- Le hub, le PDF et les liens vers l'application répondent en HTTPS.
- L'API répond sur `/health` et accepte le preflight CORS du domaine Vercel.
- Un plan réel s'affiche ; le navigateur ne contacte jamais `localhost:8000`.
- Les caches sont encore présents après un redémarrage du service Render.

Le client attend actuellement jusqu'à cinq minutes pour un plan. Les calculs plus
longs nécessiteront un traitement asynchrone avec suivi de progression ; ce montage
ne supprime pas cette limite ni les erreurs des services de données externes.

Références : [Vercel configuration](https://vercel.com/docs/project-configuration/vercel-json),
[Render Blueprints](https://render.com/docs/blueprint-spec),
[Render persistent disks](https://render.com/docs/disks).

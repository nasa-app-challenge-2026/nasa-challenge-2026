# Mettre Field Shift en ligne

Field Shift, ce sont **deux programmes** qui se parlent en HTTP :

| Partie                     | Ce que c'est                                   | Où l'héberger                                                                       |
| -------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Le front** (`frontend/`) | un site statique (build Vite dans `dist/`)     | **Vercel**, Netlify, GitHub Pages, Cloudflare Pages…                                |
| **Le serveur** (`api/`)    | l'algorithme en Python (FastAPI, numpy, scipy) | un hébergeur de **conteneurs** : Render, Railway, Fly.io, Google Cloud Run, un VPS… |

On déploie d'abord le serveur (le front a besoin de son adresse), puis le front.

## Pourquoi le serveur ne va pas sur Vercel

Les fonctions de Vercel ne conviennent pas à ce serveur :

- le premier plan d'un nouveau lieu prend **1 à 2 minutes**, le temps de télécharger ses données réelles (101 s mesurées dans le conteneur le 15 novembre 2026) ;
- il garde sur disque et en mémoire ce que les services de données ont répondu, et calcule les sections dans plusieurs processus ;
- numpy et scipy dépassent vite la taille permise d'une fonction.

Un conteneur qui tourne en continu n'a aucune de ces limites. Le fichier [`.vercelignore`](../.vercelignore) empêche Vercel de prendre le dossier `api/` pour des fonctions.

## 1. Le serveur (conteneur Docker)

L'image est décrite par [`api/Dockerfile`](../api/Dockerfile). Pour l'essayer sur sa machine :

```bash
docker build -t field-shift-api api
docker run -p 8000:8000 -e FIELD_SHIFT_CORS_ORIGINS=http://localhost:5173 field-shift-api
# http://localhost:8000/health répond {"status": "ok", …}
```

### Sur Render

1. **New → Blueprint**, puis ce dépôt : [`render.yaml`](../render.yaml) crée le service `field-shift-api` à partir du Dockerfile.
2. Remplir les variables demandées (tableau ci-dessous), au moins `FIELD_SHIFT_CORS_ORIGINS`.
3. Noter l'adresse du service (`https://field-shift-api-….onrender.com`) : c'est le `VITE_ALGO_URL` du front.

### Ailleurs (Railway, Fly.io, Cloud Run…)

Créer un service à partir du dossier **`api/`** avec son **Dockerfile**. Le serveur écoute sur le port donné par la variable `PORT` (8000 par défaut). Le chemin de santé est **`/health`**.

### Variables d'environnement du serveur

| Variable                                   | Rôle                                                                                                                                                                                                     |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FIELD_SHIFT_CORS_ORIGINS`                 | **obligatoire** : l'adresse du front, par ex. `https://field-shift.vercel.app` (plusieurs : séparées par des virgules)                                                                                   |
| `FIELD_SHIFT_CORS_ORIGIN_REGEX`            | facultatif : les déploiements de prévisualisation de Vercel, dont l'adresse change à chaque fois, par ex. `https://field-shift-[a-z0-9-]+[.]vercel[.]app`                                                |
| `FIELD_SHIFT_WORKERS`                      | processus qui calculent les sections en même temps (plans plus rapides). Mesuré : le serveur prend ~380 Mo, chaque processus ~220 Mo de plus. `0` sur une instance de 512 Mo, `1` dès 1 Go, `3` dès 2 Go |
| `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` | facultatif : un compte NASA Earthdata gratuit, pour SMAP et ECOSTRESS (sinon MERRA-2)                                                                                                                    |
| `PORT`                                     | donné par la plupart des hébergeurs ; 8000 par défaut                                                                                                                                                    |

Les adresses des services de données ont des valeurs par défaut ; elles se changent avec `FIELD_SHIFT_URL_<SOURCE>` (voir [`api/README.md`](../api/README.md)).

### Garder les données téléchargées

Le serveur garde ce que répondent les services de données dans `/data` (`FIELD_SHIFT_CACHE_DIR`, `ALGO_CACHE_DIR`, `WATER_USE_CACHE`). Sans disque persistant, ce dossier est vidé à chaque redéploiement : le premier plan d'un lieu reprend alors 1 à 2 minutes. Pour l'éviter, monter un **volume** sur `/data` (Render : _Disks_, Railway : _Volumes_, Fly.io : `fly volumes`).

### Délai de réponse

Le front attend un plan jusqu'à **5 minutes**. Le proxy de l'hébergeur doit laisser une requête durer plus de 2 minutes (le premier plan d'un lieu) : vérifier son délai maximal de requête avant de choisir. Heroku, par exemple, coupe à 30 s et ne convient pas.

## 2. Le front

### Sur Vercel

1. **Add New → Project**, importer ce dépôt. Vercel lit [`vercel.json`](../vercel.json) : build `npm run build`, dossier `dist`. Laisser la racine du projet à la racine du dépôt.
2. **Settings → Environment Variables** : `VITE_ALGO_URL` = l'adresse du serveur, **sans `/` final** (par ex. `https://field-shift-api-….onrender.com`), pour _Production_ et _Preview_.
3. Déployer. La variable est lue **au moment du build** : après l'avoir changée, redéployer.
4. Ajouter l'adresse du site (et, si besoin, le motif des prévisualisations) aux variables CORS du serveur.

### Ailleurs

N'importe quel hébergeur de site statique convient : commande de build `npm run build`, dossier publié `dist`, variable `VITE_ALGO_URL` au build. L'application utilise des adresses en `#/…` : aucune règle de réécriture n'est nécessaire. GitHub Pages est déjà prêt : [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) (voir le README).

## Vérifier

1. `https://<serveur>/health` répond `{"status": "ok", …}`.
2. Le site s'ouvre ; dans le tableau de bord, le plan arrive (la première fois pour un lieu : 1 à 2 minutes, l'animation de Rota tourne pendant ce temps).
3. Si le site dit « Impossible de joindre l'algorithme » : vérifier `VITE_ALGO_URL` (puis redéployer le front) et `FIELD_SHIFT_CORS_ORIGINS` (l'adresse exacte du site, avec `https://`).

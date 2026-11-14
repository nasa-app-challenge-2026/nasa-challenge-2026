# Message prêt à envoyer à votre Claude (équipe algo)

Copiez tout ce qui est sous la ligne, puis joignez ces fichiers du dépôt :

- `docs/ALGO_CONTRACT.md`
- `backend/contract/field-shift.schema.json`
- `backend/contract/examples/` (tous les fichiers)
- `data/reference/crops.js`
- `backend/mockEngine.js` (pour voir la forme des réponses, **pas** la logique à reprendre)

---

On participe au NASA Space Apps Challenge 2026, défi « Field Shift: Adapting Farms with NASA Data ». Notre appli aide un fermier de grandes cultures (maïs, soya, blé, orge, patate, luzerne) à planifier la rotation de chaque section de sa ferme, avec les données de la NASA.

Le front end est déjà fait. Je dois coder **l'algorithme**, qui doit respecter exactement le contrat joint (`ALGO_CONTRACT.md` et `field-shift.schema.json`).

Ce que je veux :

1. Un petit serveur en **Python avec FastAPI** qui expose `POST /evaluate`, `POST /propose` et `POST /field-data`, avec le CORS ouvert pour notre site GitHub Pages.
2. Des modèles Pydantic qui suivent le schéma JSON joint.
3. La logique, en modules séparés et testables :
   - **Données NASA** pour une section (lat/lon) : NASA POWER (sans compte) pour la météo ; GPM IMERG, SMAP, ECOSTRESS et HLS via `earthaccess` (compte Earthdata) ; SoilGrids pour le sol. Mettre les résultats en cache. Si une source ne répond pas, une valeur par défaut documentée et un drapeau, pas un plantage.
   - **Effet des enchaînements de cultures** à partir des études (voir `data/reference/sources.js` du front), sans jamais écrire le nom d'une étude dans les messages renvoyés.
   - **Scores** eau, sol, résilience, revenu (0 à 100), pondérés par les priorités du fermier.
   - **Comparaisons** avec le maïs en continu et la rotation maïs-soya.
   - **Stress test** : normal, sec, chaud, ravageurs, sur 1 ou 3 ans (`options.stressYears`).
   - **Proposition** de rotation pour une durée donnée, qui respecte les délais de retour de `crops.js`, n'utilise que la réserve de semences du fermier (`farm.seeds`, sinon `missingSeeds`), ne répète pas la culture actuelle de la section (`currentCrop`) la première année, et suit l'ordre de ses priorités.
4. Des tests (pytest) qui passent les fichiers de `backend/contract/examples/*.input.json` et valident chaque réponse contre le schéma.
5. Un README qui explique comment lancer le serveur et chaque formule, avec ses sources.

Contraintes : `meta.demo` vaut `false` ; un résultat par section, dans le même ordre ; les fourchettes sont `[bas, haut]` ; la confiance baisse d'un niveau à partir de 15 ans. Quand une valeur est une hypothèse, indique-le dans le code et dans le README.

Pour vérifier, notre front a une commande : `npm run check:algo -- http://localhost:8000`. Elle doit afficher « Tout respecte le contrat ».

# RotaAI

## Aujourd'hui : réponses écrites à l'avance

- [`data/reference/rotaaiAnswers.js`](../data/reference/rotaaiAnswers.js) : les questions proposées par écran (`SUGGESTED`) et une vingtaine de réponses (`INTENTS`), trouvées par mots-clés, sans accents ni majuscules.
- [`frontend/ui/rotaai.js`](../frontend/ui/rotaai.js) : le bouton et le panneau.
- Les réponses expliquent l'algorithme v5.1 (jumeaux climatiques, sigma, cycles, délais de retour, garder ou changer, robustesse…). Les tests vérifient que chaque question proposée a une vraie réponse et qu'aucune réponse ne cite une étude.

Ajouter une réponse : un objet `{ keys, text, sources }` dans `INTENTS`. Les mots-clés les plus précis vont en haut de la liste.

**Avant la vidéo :** Nour et Yanis relisent les réponses, pour qu'elles décrivent exactement l'algorithme (`docs/ALGORITHME.md`).

## Plus tard : un vrai modèle d'IA (optionnel)

1. Un petit serveur (fonction Cloudflare Worker ou Vercel) garde la clé de l'API **secrète**. Ne jamais mettre une clé dans le code du site : n'importe qui pourrait la lire.
2. Le front envoie la question, l'écran courant et le plan de la section (`FarmPlan`), pour que les réponses parlent de la ferme du fermier.
3. Les réponses écrites à l'avance restent la solution de secours si le serveur ne répond pas.
4. À déclarer dans la section sur l'utilisation de l'IA de la soumission.

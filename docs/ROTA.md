# Rota

Rota est l'assistant de l'appli. **Les écrans n'expliquent rien eux-mêmes** : là où il y aurait une explication, il y a un petit bouton « Demander à Rota ». Rota s'ouvre, affiche la question et y répond.

## Aujourd'hui : réponses écrites à l'avance

- [`data/reference/rotaAnswers.js`](../data/reference/rotaAnswers.js) :
  - `TOPICS` : ce qu'expliquent les boutons « Demander à Rota » (une question et sa réponse par sujet) ;
  - `INTENTS` : une vingtaine de réponses aux questions libres, trouvées par mots-clés, sans accents ni majuscules ;
  - `SUGGESTED` : les questions proposées par écran ;
  - `OUT_OF_MVP` : « Hors de portée du MVP. », ce que Rota répond quand le fermier touche une fonction que le MVP n'a pas (un autre type de ferme, « Mot de passe oublié »). Aucun écran n'écrit « bientôt ».
- [`frontend/ui/rota.js`](../frontend/ui/rota.js) : le bouton flottant, le panneau, et les deux boutons des écrans : `askRota('sujet')` (avec son libellé) et `askRotaIcon('sujet')` (rond, là où un libellé ne tient pas).
- [`frontend/actions.js`](../frontend/actions.js) : `rota-explain` (un sujet de `TOPICS`), `rota-mvp` (hors MVP), `rota-ask` et `rota-send` (questions libres).

Les réponses expliquent l'algorithme v5.1 (jumeaux climatiques, sigma, cycles, délais de retour, garder ou changer, robustesse, eau, ravageurs…). Les tests (`tests/rota.test.js`) vérifient que :

- chaque bouton « Demander à Rota » d'un écran ouvre un sujet qui existe ;
- chaque question proposée a une vraie réponse ;
- aucune réponse ne cite une étude ;
- aucun fichier n'écrit « bientôt ».

### Ajouter une explication à un écran

1. Un sujet dans `TOPICS` : `'mon-sujet': { q: 'La question ?', text: 'La réponse.', sources: true }` (`sources` ajoute le lien vers « Détail et sources »).
2. Dans l'écran : `${askRota('mon-sujet')}`. Aucun texte d'explication dans l'écran.

Ajouter une réponse à une question libre : un objet `{ keys, text, sources }` dans `INTENTS`. Les mots-clés les plus précis vont en haut de la liste.

**Avant la vidéo :** Nour et Yanis relisent les réponses, pour qu'elles décrivent exactement l'algorithme (`docs/ALGORITHME.md`).

## Plus tard : un vrai modèle de langage (optionnel)

1. Un petit serveur (fonction Cloudflare Worker ou Vercel) garde la clé de l'API **secrète**. Ne jamais mettre une clé dans le code du site : n'importe qui pourrait la lire.
2. Le front envoie la question, l'écran courant et le plan de la section (`FarmPlan`), pour que les réponses parlent de la ferme du fermier.
3. Les réponses écrites à l'avance restent la solution de secours si le serveur ne répond pas.
4. À déclarer dans la section sur l'utilisation de l'IA de la soumission.

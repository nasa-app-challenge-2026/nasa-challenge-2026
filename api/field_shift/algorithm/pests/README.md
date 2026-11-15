# Mesure « ravageurs »

Note une rotation de **0 (pire) à 1 (meilleur)** selon la pression des maladies du sol, des nématodes et des insectes que ses cultures laissent s'accumuler. C'est la mesure `ravageurs` du classement des rotations (`POST /rotations/rank`, `POST /measures/ravageurs`). La route la renvoie sur 100.

## En une phrase

Chaque organisme a une pression entre 0 et 1 dans le champ. Elle monte quand une culture hôte pousse et baisse quand le champ passe une année sans hôte. Chaque culture est pénalisée par la pression qu'elle trouve au moment où elle commence.

## Branchement

La mesure se branche comme `protection_sol`, sans autre changement dans le classement :

```
ranking/measures.py   PestsMeasure.evaluate(rotation, context)
   └─ pests/pest_measure.py      Rotation (mois) → cultures par année → critère
        └─ pests/pest_criterion.py   pression, risque, score, phrases
```

## Entrées

| Entrée | D'où elle vient |
|---|---|
| La rotation (phases en mois) | la requête (`Rotation`) |
| Le catalogue des organismes | `pest_data.py` |

Le contrat du classement ne donne **ni historique de la parcelle, ni maladie déclarée**. La rotation est donc prise comme déjà en place depuis plusieurs cycles. Le code sait gérer l'historique et les maladies déclarées (voir les tests), mais rien ne les lui envoie aujourd'hui. La durée de la simulation ne change pas le résultat : on mesure la rotation une fois qu'elle se répète.

## Des mois aux années (`pest_measure.py`)

On applique la même règle que l'ancien plan (`chain_step.to_occupations`) :
- une culture récoltée compte l'année de sa récolte (la fin de sa phase) ;
- une pérenne (luzerne, foin) compte de son semis à sa dernière récolte ;
- le sol nu, la jachère travaillée et les couverts (`seigle`) comptent comme des années sans hôte ;
- une culture compte comme son espèce (soya 2e = soya).

Un cycle qui ne fait pas un nombre entier d'années (30 mois, par exemple) est rejoué jusqu'à en faire un (2 × 30 mois = 5 ans).

## Le calcul (`pest_criterion.py`, `pressure_model.py`)

**1. La ligne du temps.** Elle enchaîne trois périodes :
- la rotation jouée 4 fois avant ;
- la rotation ;
- la rotation répétée au cycle suivant.

**2. La pression de chaque organisme, année par année :**

```
année avec hôte   P = min(1, P + croissance × sensibilité)
année sans hôte   P = P × d,    d = ε^(1/L)
```

- `L` est le nombre d'années sans hôte conseillé par la source pour cet organisme.
- `ε = 0.1` : après `L` années sans hôte, une pression pleine tombe à 10 %.
- `croissance = 1` : une année d'hôte principal remplit la pression.

**3. Le risque d'une culture.** On lit la pression de chaque organisme qu'elle accueille, au début de sa première année :

```
R = Σ (sévérité × sensibilité × P) / Σ (sévérité × sensibilité)
```

**4. Le score.** On prend `S = 1 − moyenne des R` :
- 50 % sur la rotation ;
- 50 % sur sa répétition.

Une culture qu'aucun organisme connu n'accueille a un risque de 0.

## Sortie (`MeasureResult`)

- `score` : de 0 à 1.
- `value` : vide. La mesure n'a pas d'unité, le score suffit.
- `note` : les cultures sans donnée, puis au plus 6 phrases pour le fermier, les cultures les plus exposées en premier. Exemple : « Soya -1 puis Soya 1 : moisissure blanche, 1 an sans hôte pour 5 conseillés, pression moyenne. »
- **Non disponible** (`available: false`) dans deux cas, et la mesure sort alors du total comme une mesure pas encore écrite :
  - la rotation n'a aucune culture récoltée (seulement des couverts ou du sol nu) ;
  - le catalogue ne connaît aucune de ses cultures (une prairie de `foin`). Un score de 100 voudrait alors dire « inconnu », pas « sain ».

## Exemples réels

Calculés avec ce code, sur 100 :

| Rotation | Score |
|---|---|
| maïs en continu | 0 |
| maïs – soya | 64,3 |
| maïs – soya – blé d'automne | 72,2 |
| maïs – soya – blé d'automne – canola | 76,4 |
| maïs – soya – blé d'automne – canola – luzerne | 85,0 |

## Le catalogue (43 organismes, `pest_data.py`)

- **20 maladies du sol** de SARE (McGrath 2009, annexe 3), dont le nématode à kyste du soya. `L` est la borne haute de l'intervalle SARE.
- **22 « complexes de culture »** issus de Fruchtfolge (Pahmeyer, Kuhn & Britz 2021) : la pause qu'il faut entre deux mêmes cultures, sans cause nommée.
- **1 insecte** : la chrysomèle des racines du maïs, avec `L = 1`. Sources : Agri-Réseau 118135 et 118489, MAPAQ 2007-2008, Iowa State University.

Chaque organisme garde ses sources dans le champ `sources`. Le catalogue ne connaît aucun organisme pour trois cultures : `foin`, `jachere` et `soya-2e` (ce dernier est compté comme `soya`).

**Volontairement non codés :**
- les variantes de chrysomèle résistantes à la rotation (non détectées au Québec selon le MAPAQ) ;
- les vers fil-de-fer (aucune source ne donne de nombre d'années sans hôte).

## Limites connues (décisions d'équipe)

- **Sévérité neutre** : elle vaut 1 pour tous les organismes, car les pertes de rendement publiées ne sont pas comparables entre elles (gardées dans `reported_yield_loss`, non utilisées). Tous les hôtes ont aussi une sensibilité de 1.
- **Dilution** : une culture qui accueille plusieurs organismes moyenne leurs pressions. Un seul organisme à pression pleine pèse donc peu. Le paramètre `worst_case_weight` (0 par défaut) permet de donner plus de poids au pire organisme. Une culture sans donnée, dans une rotation qui en a d'autres, compte comme sans risque et tire la moyenne vers le haut. La note le signale.
- **Deux cultures récoltées la même année** lisent toutes les deux la pression du début de l'année.
- **Une seule vitesse de décroissance** : le modèle ne reproduit pas les deux vitesses des spores de hernie.
- Les tables SARE et Fruchtfolge n'ont pas été revérifiées contre les documents originaux, et aucun agronome n'a validé les résultats.

## Fichiers

| Fichier | Rôle |
|---|---|
| `pest_measure.py` | rotation → cultures par année → critère ; la note |
| `pest_criterion.py` | risque, score, détails, confiance |
| `pressure_model.py` | pression année par année (fonction pure) |
| `pest_timeline.py` | ligne du temps (avant, rotation, cycle suivant) |
| `pest_catalog.py` | index « culture → organismes » |
| `pest_data.py` | catalogue des organismes et sources |
| `pest_settings.py` | paramètres (ε, croissance, poids 50/50, 4 cycles d'avance…) |
| `pest_result.py` | résultat interne du critère |
| `pest_explanations.py` | phrases pour le fermier |

Tests : `api/tests/test_pests.py` (le modèle) et `api/tests/test_pest_measure.py` (le branchement).

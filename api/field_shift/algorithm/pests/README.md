# Mesure « ravageurs »

Note une rotation de **0 (pire) à 1 (meilleur)** selon la pression des maladies du sol, des nématodes et des insectes que ses cultures laissent s'accumuler. C'est la priorité `ravageurs` du plan (`POST /plan`) et la mesure `ravageurs` du classement des rotations (`POST /rotations/rank`, `POST /measures/ravageurs`). Les routes la renvoient sur 100.

## En une phrase

Chaque organisme a une pression entre 0 et 1 dans le champ. Elle monte quand une culture hôte pousse et baisse quand le champ passe une année sans hôte. Chaque culture est pénalisée par la pression qu'elle trouve au moment où elle commence.

## Branchement

Dans le plan, chaque chaîne de la recherche en faisceau est notée sur les quatre priorités ; la priorité `ravageurs` est ce critère :

```
chain/chain_scorer.py   score_chain(chain, ctx)
   └─ chain/cycle_context.py     CycleContext.pests : un PestCriterion par parcelle et par cycle
        └─ pests/pest_criterion.py   pression, risque, score, phrases
```

Dans le classement, la mesure se branche comme `protection_sol`, sans autre changement :

```
ranking/measures.py   PestsMeasure.evaluate(rotation, context)
   └─ pests/pest_measure.py      Rotation (mois) → cultures par année → critère
        └─ pests/pest_criterion.py   pression, risque, score, phrases
```

## Entrées

| Entrée | D'où elle vient |
|---|---|
| La chaîne du plan (cultures par année) | la recherche en faisceau (`chain_step.to_occupations`) |
| L'historique et les maladies déclarées de la parcelle | le plan (`POST /plan`), par le `ReturnDelayChecker` du cycle |
| La rotation du classement (phases en mois) | la requête (`Rotation`) |
| Le catalogue des organismes | `pest_data.py` |

**Dans le plan**, la chaîne est mesurée après ce qui a poussé avant dans la parcelle, et une maladie que le fermier déclare part d'une pression pleine au début de la chaîne. Une chaîne partielle (en cours de construction) est notée sans sa répétition au cycle suivant ; les phrases ne sont écrites que pour les chaînes complètes.

**Le contrat du classement** ne donne ni historique de la parcelle, ni maladie déclarée. La rotation est donc prise comme déjà en place depuis plusieurs cycles. La durée de la simulation ne change pas le résultat : on mesure la rotation une fois qu'elle se répète.

## Des mois aux années (`pest_measure.py`)

Pour le classement, on applique la même règle que le plan (`chain_step.to_occupations`) :
- une culture récoltée compte l'année de sa récolte (la fin de sa phase) ;
- une pérenne (luzerne, foin) compte de son semis à sa dernière récolte ;
- le sol nu, la jachère travaillée et les couverts (`seigle`) comptent comme des années sans hôte ;
- une culture compte comme son espèce (soya 2e = soya).

Un cycle qui ne fait pas un nombre entier d'années (30 mois, par exemple) est rejoué jusqu'à en faire un (2 × 30 mois = 5 ans).

## Le calcul (`pest_criterion.py`, `pressure_model.py`)

D'où vient le modèle, en bref :
- le **principe** vient de SARE (McGrath) : cultiver des non-hôtes jusqu'à ce que le pathogène du sol meure ou tombe à un niveau sans dégât ;
- la **forme exponentielle** de la baisse est classique en épidémiologie et observée pour plusieurs pathogènes du sol ;
- les **formules exactes et leurs valeurs** (`ε`, `g`, 50/50…) sont une proposition de l'équipe (`REVAMP_ALGO_RAVAGEURS.md`, document de conception de l'équipe gardé hors du dépôt, section 4.2, marquée « PROPOSITION »), sans étude qui les fixe.

Détail en fin de fichier, section Sources.

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

## Sortie

Dans le plan, chaque chaîne porte `pests` (contrat `FarmPlan`) : la note (0 à 1), la confiance (part des cultures que le catalogue connaît), les cultures sans donnée et les phrases. L'écran « Plan par cycle » affiche les cultures les plus exposées. `pests` vaut `null` quand le catalogue ne connaît aucune culture de la chaîne : la priorité est alors laissée hors de la moyenne.

Dans le classement (`MeasureResult`) :

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

Tests : `api/tests/test_pests.py` (le modèle), `api/tests/test_pest_measure.py` (le classement) et `api/tests/test_plan_pests.py` (le plan).

## Sources

### A. Données utilisées dans le calcul

- **SARE, annexe 3** : McGrath, M. T. (2009). *Sources of Inoculum for Crop Diseases in the Northeastern United States*, annexe 3 (p. 124-137). Dans Mohler, C. L. et Johnson, S. E. (dir.), *Crop Rotation on Organic Farms: A Planning Manual*, NRAES-177, SARE. https://www.sare.org/wp-content/uploads/Crop-Rotation-on-Organic-Farms.pdf
  → les 20 maladies du sol, leurs cultures hôtes et leurs années sans hôte. `L` est la borne haute.
- **Fruchtfolge** : Pahmeyer, C., Kuhn, T. et Britz, W. (2021). 'Fruchtfolge': A crop rotation decision support system for optimizing cropping choices with big data and spatially explicit modeling. *Computers and Electronics in Agriculture*, 181, 105948. https://doi.org/10.1016/j.compag.2020.105948
  → la pause entre deux mêmes cultures (22 « complexes de culture »).
- **Chrysomèle des racines du maïs** (`L = 1`, maïs seul hôte) :
  - Agri-Réseau, *Les chrysomèles des racines du maïs en grandes cultures* (document 118135). https://www.agrireseau.net/documents/Document_118135.pdf
  - Agri-Réseau, *Une seule année de soya réduit drastiquement les populations de chrysomèles* (document 118489). https://www.agrireseau.net/documents/Document_118489.pdf
  - MAPAQ, *Rapport de dépistage de la chrysomèle des racines du maïs dans le maïs et le soya au Québec en 2007 et 2008* : la variante soya n'a pas été détectée. Pas de lien vérifié.
  - Iowa State University, *Corn rootworm life cycle*. https://cornrootworm.extension.iastate.edu/basics/life-cycle

Les tables SARE et Fruchtfolge étaient déjà dans le repo (`reference/return_delays.py`). Elles n'ont pas été revérifiées ligne par ligne contre les documents originaux.

### B. Fondement du modèle (principe et forme de la baisse)

Ces sources appuient le principe et la forme. Aucune ne fixe les formules exactes ni les valeurs utilisées ici.

- **Principe** : McGrath, M. T. (2009). *Managing Plant Diseases with Crop Rotation*. Dans *Crop Rotation on Organic Farms* (SARE). https://sare.org/publications/crop-rotation-on-organic-farms/physical-and-biological-processes-in-crop-production/managing-plant-diseases-with-crop-rotation/
  → on cultive des non-hôtes jusqu'à ce que le pathogène meure ou tombe à un niveau sans dégât notable. C'est l'idée derrière « après `L` ans sans hôte, la pression tombe à `ε` ».
- **Modèle exponentiel de l'inoculum** : APS Education Center, *Mathematical Models* (épidémiologie temporelle). https://apsnet.org/edcenter/EpidemiologyTemporal/Pages/MathematicalModels.aspx
  → l'inoculum d'une saison à l'autre varie à un taux négatif pendant une rotation vers une culture non hôte, ce qui donne une fonction exponentielle.
- **Baisse exponentielle observée** : étude sur la survie des microsclérotes de *Verticillium dahliae* dans le sol (KNPV, 2020). https://ppc.nwsuaf.edu.cn/docs/2020-06/40f9f6f0a38540b1b2aa67ed689eacb5.pdf
  → la survie suit un modèle de déclin exponentiel négatif.
- **Nématode à kyste du soya** :
  - De Bruin, J. L. et Pedersen, P. (2008), *Agronomy Journal*. https://www.mssoy.org/sites/default/files/documents/debruin-1-agron-j.pdf → cite des modèles exponentiels décroissants (Appel et Lewis 1984 ; Chen et al. 2001).
  - Ohio State University Extension, *Soybean Cyst Nematode* (PLPATH-SOY-5). https://ohioline.osu.edu/factsheet/plpath-soy-5 → baisse d'environ 50 % par an sous non-hôte. Le modèle donne environ 44 % par an pour `L = 4` : c'est cohérent.

### C. Chiffres gardés mais non utilisés par le score

- Farm Progress, *6 ways to manage soybean cyst nematode* (jusqu'à 30 % de pertes). https://farmprogress.com/crop-disease/6-ways-to-manage-soybean-cyst-nematode
- Dill-Macky, R. et Jones, R. K. (2000). The effect of previous crop residues and tillage on Fusarium head blight of wheat. *Plant Disease*, 84(1), 71-76. https://doi.org/10.1094/PDIS.2000.84.1.71
  → blé environ 15 % moins productif après maïs ou blé qu'après soya. Confirme aussi le risque du blé après maïs.
- AAC Normandin (hernie : environ 90 % des spores disparues après 2 ans, le reste très durable) et PNW Plant Disease Handbook (demi-vie de 3 à 6 ans). Cités dans `pest_data.py`, sans lien vérifié.

### D. Ce que la littérature dit et que le modèle ne capte pas

- Francl, L. J. et Dropkin, V. H. (1986), *Plant Disease*, 70, 791 : la baisse sans hôte dépend de la densité de départ. https://apsnet.org/publications/plantdisease/backissues/Documents/1986Abstracts/PD_70_791.htm
- Koenning, S. R. et al. (1995) : les populations fluctuent de façon imprévisible d'une année à l'autre. https://agris.fao.org/search/ru/records/65dfc2240f3e94b9e5dbf06c
- Köhl, J. et al. (2024), *Frontiers in Agronomy*, 6 : les résidus de non-hôtes peuvent servir de pont aux pathogènes. https://doi.org/10.3389/fagro.2024.1470598
- Ohio State (ci-dessus) : sur hôte sensible, la population est multipliée par 10 à 40 par an. La montée réelle est multiplicative, alors que le modèle la rend linéaire et plafonnée à 1.

### E. Ce qui ne vient d'aucune source

Ce sont des choix, à présenter comme tels :
- **Formules et valeurs de `REVAMP_ALGO_RAVAGEURS.md`** (section 4.2, marquée « PROPOSITION ») : `P = min(1, P + g × s)`, `P × ε^(1/L)`, le risque pondéré `R`, `ε = 0,1`, `g = 1`. Le document ne cite aucune étude pour cette partie. Seules ses données citent SARE et Fruchtfolge.
- **Choix d'implémentation** :
  - le poids 50/50 entre la rotation et sa répétition ;
  - la rotation jouée 4 fois avant (le MD proposait 2) ;
  - une sévérité de 1 pour tous les organismes (le MD voulait la tirer des guides de lutte intégrée) ;
  - une maladie déclarée qui met la pression à 1 ;
  - une culture inconnue comptée comme sans risque, et le foin « non disponible » ;
  - le passage des mois aux années, repris de l'ancien algo.
- **Validation** : aucune contre des observations de terrain. Elle était prévue par le MD (section 4.6, « comparer à des données publiées »).

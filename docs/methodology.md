# Méthodologie

Tout seuil, formule ou affirmation est rattaché à un identifiant de `data/reference/sources.yaml`.
Une valeur non documentée reste **inconnue** ; une hypothèse de l'équipe est marquée
**provisoire** et affichée comme telle.

## 1. Données

Températures quotidiennes T2M, T2M_MAX, T2M_MIN (°C) et précipitations PRECTOTCORR (mm/jour) de
NASA POWER, heure solaire locale, 1981–2025, cellule MERRA-2 de 0,5° × 0,625° (~56 × 46 km à
48° N). Seules les années **sans aucune valeur manquante** sont analysées (aucune imputation).

## 2. Indicateurs annuels (`domain/climate/indicators.py`)

Moyenne quotidienne des indices agroclimatiques : `Tmoy = (Tmax + Tmin) / 2` [aafc_agroclimate].

| Indicateur | Définition | Source |
|---|---|---|
| Degrés-jours base B | `Σ max(0, Tmoy − B)`, 1er avril–31 octobre, B = 0, 5, 10 °C, sans plafond | aafc_agroclimate, omafra_fieldcropnews_2025 |
| UTM | `(Ymax + Ymin)/2`, `Ymax = 3,33(Tmax−10) − 0,084(Tmax−10)²` si Tmax ≥ 10 sinon 0 ; `Ymin = 1,8(Tmin−4,44)` si Tmin ≥ 4,44 sinon 0. Début : 1er jour, après la date médiane du dernier gel (30 dernières années), où la moyenne mobile de 5 jours ≥ 12,8 °C. Fin : 1er jour après le 15 juillet avec Tmin ≤ −2 °C | bourgeois_2012, omafra_93_119 |
| Jours de gel | Tmin < 0 °C (FD) | etccdi_indices |
| Dernier gel / premier gel | Dernier jour avant le 15 juillet / premier jour à partir du 15 juillet avec Tmin < 0 °C (le pivot du 15 juillet est une convention de l'équipe) | plouffe_2011 |
| Saison sans gel | Jours strictement entre les deux | plouffe_2011 |
| Saison de croissance | GSL : 1er épisode de 6 jours > 5 °C (avant le 1er juillet) jusqu'au 1er épisode de 6 jours < 5 °C après le 1er juillet | etccdi_indices |
| Précipitations | Annuelles, saisonnières, avril–octobre ; jours ≥ 1 mm ; plus longue période < 1 mm (CDD) ; jours ≥ 20 mm (R20mm) ; Rx1day | etccdi_indices |
| ETo et bilan hydrique | Hargreaves (FAO-56 éq. 52) avec Ra (éq. 21–25) ; bilan = P − ETo, avril–octobre. Ordre de grandeur : la méthode tend à surestimer en climat humide | fao56 |
| Jours de fauche possibles | Jours du 1er juin au 31 juillet qui ouvrent ≥ 3 jours consécutifs < 1 mm | cqpf_hay_guide_2002 |

Résumés : médiane, centiles 20 et 80 (« 8 années sur 10 », méthode linéaire type 7), tendance
de Theil-Sen par décennie et test de Mann-Kendall (≥ 10 ans) [audet_2012]. Une tendance
significative décrit le passé, elle n'est pas extrapolée.

## 3. Contrôles par culture et par année (`agronomy/suitability.py`)

Dates de semis inconnues : la saison est déduite de la météo de chaque année.

- **Chaleur pour mûrir** (annuelles) : cultures fraîches = DJC base 0 du début de la saison de
  croissance jusqu'au premier gel ≤ −2 °C ; soya et maïs = UTM de la saison UTM. Comparée à la
  plage documentée : *insuffisante* (< min), *juste* (dans la plage), *suffisante* (≥ max).
  Le début de saison thermique précède le semis réel : le test est **optimiste**, un manque
  signalé est donc robuste.
- **Gel dommageable** (annuelles) : au moins un jour au seuil de dommage documenté entre le début
  de la saison de la culture et le 14 juillet.
- **Fourragères pérennes** : pas de maturité à atteindre (*non applicable*) ; gel, survie à
  l'hiver et météo de fenaison **non évalués** et listés comme risques non chiffrés.

| Culture | Chaleur | Gel | Eau (indicatif) |
|---|---|---|---|
| Avoine / orge / blé | DJC0 1483–1738 / 1269–1522 / 1538–1665 [msu_mt200103] | < −6 °C [manitoba_spring_frost] | 450–650 mm [fao_irrigation_water_needs] |
| Pois sec | DJC0 1527–1686 [msu_mt200103] | < −6 °C **provisoire** (analogie) | 350–500 mm |
| Soya hâtif | 2300–2550 UTM [guide_soya_2024, rgcq_soya_2021] | ≤ −2 °C **provisoire** | 450–700 mm |
| Maïs-grain | 2300–2500 UTM [plouffe_2011] | ≤ −2 °C [manitoba_spring_frost] | 500–800 mm |
| Luzerne | — | non documenté | 800–1600 mm |
| Foin (non précisé), prairie fléole–trèfle | — | non documenté | non documenté |

## 4. Stress test historique (`simulation/stress_test.py`)

Une rotation de n ans = n champs de même surface, un par phase. Exposition d'une année = part
des champs dont la culture a eu un manque de chaleur ou un gel dommageable. Résultats : série
annuelle, moyenne, centile 80, maximum, nombre d'années touchées, 3 pires années. **Ce n'est pas
un rendement.**

## 5. Classement multicritère (`simulation/assessment.py`, `comparison.py`)

1. **Contraintes bloquantes** (modèles uniquement ; la rotation actuelle est toujours évaluée) :
   culture exclue par l'agriculteur ; culture annuelle dont la chaleur minimale documentée manque
   **plus d'une année sur deux** (la cote OMAFRA est atteinte une année sur deux).
2. **Scores de 0 à 1** :
   - résilience climatique = `1 − exposition moyenne` ;
   - santé du sol = moyenne de (part en prairie pérenne, part en légumineuse, diversité
     `min(1, (familles − 1)/2)`) — indicateurs de **pratiques** reconnues [quebec_forages,
     fao_conservation_agriculture], pas une mesure du sol ; légumineuse inconnue = non créditée ;
   - conservation de l'eau = `1 − (besoin moyen − 400)/(1200 − 400)` borné, sur les besoins
     indicatifs FAO ; **utilisé seulement si documenté pour toutes les cultures comparées** ;
   - revenu potentiel : **non évalué** (aucune donnée économique).
   Les bornes 400–1200 mm et la cible de 3 familles sont des **conventions de l'équipe**
   (`ScoringPolicy`), de même que le seuil « à risque » (> 1 année sur 5, `ScreeningPolicy`).
3. **Score pondéré** = moyenne des critères utilisables pondérée par les priorités (0–3).
4. **Sélection** : alternative 1 = meilleur score à poids égaux climat + sol ; alternative 2 =
   meilleur score selon les priorités parmi les restantes ; égalités départagées par l'ordre du
   catalogue (déterministe).

Principe de **prudence asymétrique** : un bénéfice inconnu n'est jamais crédité ; un risque
inconnu n'est jamais compté comme absent, il est listé.

## 6. Explications (`simulation/explanations.py`)

Chaque phrase est produite à partir d'un écart calculé (ex. « 75 % contre 67 % ») ou d'une
propriété sourcée, et porte ses identifiants de source. Pas de phrase si l'écart est nul (seuil
de 1 point de pourcentage pour l'exposition). Aucune IA générative.

## 7. Résultats sur la ferme de démonstration (1981–2025, instantané versionné)

- UTM : médiane 2193, 8 ans sur 10 ≥ 1928 ; tendance +169 UTM/décennie (p < 0,001) ; 2024 : 2886.
- Saison sans gel : médiane 152 jours (+5,9 jours/décennie) ; saison de croissance : 168 jours.
- Soya hâtif : chaleur minimale (2300 UTM) **non atteinte 28 années sur 45** → écarté, ce qui
  rejoint l'échec déclaré par l'agriculteur. Les dernières années sont plus chaudes : à suivre,
  sans extrapolation.
- Juin–juillet 2024 : à l'échelle de la cellule, 24 jours de pluie (médiane 29) et 15 jours de
  fauche possibles (médiane 10) : **les données ne montrent pas une année exceptionnelle**, alors
  que l'agriculteur rapporte des orages fréquents. Les orages sont locaux et brefs ; une cellule
  de ~50 km les lisse. L'observation reste valable et motive un capteur ou des données locales
  (phase 3).
- Résultat de la comparaison : les céréales ne rencontrent aucune contrainte documentée ; le
  classement est donc porté par les pratiques favorables au sol, et le critère « eau » est exclu
  faute de besoin documenté pour le foin.

## 8. Limites

Pas de mesure à la ferme, sols non analysés, seuils de maturité issus d'essais en Saskatchewan,
risques des prairies (hiver, fenaison) non chiffrés, aucune donnée économique, hémisphère sud
non pris en charge. Voir aussi `METHOD_LIMITS_FR`, affiché avec chaque résultat.

/**
 * The four priorities the farmer ranks (step 1, block D): the same four as the measures of the
 * algorithm server. The algorithm turns the ranking into weights (rank order centroid) and scores
 * every chain on each priority (0 to 1).
 */
export const CRITERIA = {
  rendement: {
    label: 'Rendement',
    text: 'Chaque culture aide-t-elle la suivante ? L’effet du précédent mesuré par satellite dans les champs de la région.',
    icon: 'M3 17l6-6 4 4 8-8M14 7h7v7',
  },
  eau: {
    label: 'Utilisation de l’eau',
    text: 'Des cultures qui demandent peu d’eau, résistent aux sécheresses et gardent la pluie dans le sol.',
    icon: 'M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5S12.5 5 12 2.5C11.5 5 10 7.4 8 9 6 10.6 5 12.5 5 15a7 7 0 0 0 7 7Z',
  },
  protection_sol: {
    label: 'Protection du sol',
    text: 'Garder le sol couvert par une culture vivante le plus longtemps possible, contre l’érosion.',
    icon: 'M3 12a9 9 0 0 1 18 0ZM12 12v7a2 2 0 0 0 4 0',
  },
  ravageurs: {
    label: 'Ravageurs',
    text: 'Éviter que les maladies, nématodes et insectes du sol s’accumulent : chaque culture trouve le moins de pression possible.',
    icon: 'M12 13a5 5 0 1 0 0 10 5 5 0 0 0 0-10ZM12 13V9M8 9h8M9 9 7 5M15 9l2-4M7 16H3M21 16h-4',
  },
};

/** Fixed order of the priorities (the CriterionId of the contract). */
export const CRITERIA_IDS = ['rendement', 'eau', 'protection_sol', 'ravageurs'];

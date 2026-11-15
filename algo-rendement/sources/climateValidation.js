/** Une saison manquante ne doit ni devenir une sécheresse, ni décaler le calendrier. */
export function validateClimateSeasons(seasons, { startYear, endYear } = {}) {
  if (!Array.isArray(seasons) || seasons.length < 1 || seasons.length > 86) {
    throw new RangeError('Saisons climatiques invalides : 1 à 86 saisons attendues.');
  }
  for (let i = 0; i < seasons.length; i++) {
    const s = seasons[i];
    if (
      !s ||
      !Number.isInteger(s.year) ||
      s.year < 1981 ||
      s.year > 2100 ||
      !['meanTempC', 'gddBase10', 'heatStressDays', 'precipMm'].every((k) =>
        Number.isFinite(s[k]),
      ) ||
      s.gddBase10 < 0 ||
      s.heatStressDays < 0 ||
      s.heatStressDays > 153 ||
      s.precipMm < 0 ||
      (i > 0 && s.year !== seasons[i - 1].year + 1)
    ) {
      throw new RangeError(
        'Saisons climatiques incomplètes, non consécutives ou valeurs manquantes.',
      );
    }
  }
  if (
    (startYear !== undefined && seasons[0].year !== startYear) ||
    (endYear !== undefined && seasons.at(-1).year !== endYear)
  ) {
    throw new RangeError('La série climatique ne couvre pas toutes les années demandées.');
  }
  return seasons;
}

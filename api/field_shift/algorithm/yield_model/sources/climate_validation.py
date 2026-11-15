"""A missing climate year must never shift a rotation's calendar."""
from field_shift.algorithm.yield_model.config import is_finite, is_integer


def validate_climate_seasons(seasons, *, start_year=None, end_year=None):
    if not isinstance(seasons, list) or not 1 <= len(seasons) <= 86:
        raise ValueError("Saisons climatiques invalides : 1 à 86 saisons attendues.")
    for i, season in enumerate(seasons):
        if (not isinstance(season, dict) or not is_integer(season.get("year"))
            or not 1981 <= season["year"] <= 2100
            or not all(is_finite(season.get(k)) for k in
                       ("meanTempC", "gddBase10", "heatStressDays", "precipMm"))
            or season["gddBase10"] < 0 or not 0 <= season["heatStressDays"] <= 153
            or season["precipMm"] < 0
            or (i and season["year"] != seasons[i - 1]["year"] + 1)):
            raise ValueError("Saisons climatiques incomplètes, non consécutives ou valeurs manquantes.")
    if ((start_year is not None and seasons[0]["year"] != start_year)
        or (end_year is not None and seasons[-1]["year"] != end_year)):
        raise ValueError("La série climatique ne couvre pas toutes les années demandées.")
    return seasons

"""What the web layer calls to rank rotations: reads the request, gathers the conditions of each
section, runs the ranking and writes the answer.

The conditions of a section come from three places:
    1. the section itself (the `site` object of the request), which always wins;
    2. the data services, called only for what the section does not give (SoilGrids, Copernicus
       DEM, NASA POWER, MODIS), at the centre and over the outline of the section;
    3. a published model, for Ksat, K and R when neither gives them (see `site_estimates`).
There is no default value: a service that fails makes the request fail (502, `SectionDataError`).
The answer says, value by value, where it came from and how it was computed.
"""

from __future__ import annotations

from collections.abc import Sequence

from field_shift.algorithm.ranking.measures import Measure, SectionContext, all_measures
from field_shift.algorithm.ranking.rotation_ranker import rank_rotations
from field_shift.algorithm.soil_protection.site_conditions import (
    SITE_VARIABLES,
    SiteReading,
    site_from_readings,
)
from field_shift.algorithm.soil_protection.site_estimates import ESTIMATED_FROM, with_estimates
from field_shift.contract.ranking_mapper import (
    RankingRequest,
    ranked_rotation_out,
    read_ranking_input,
    section_readings,
    site_notes,
    site_out,
)
from field_shift.contract.rotation_ranking import (
    PointOut,
    RankingInput,
    RankingMetaOut,
    RankingSectionInput,
    RotationRanking,
    SectionRankingOut,
)
from field_shift.data_access.site_data import SiteDataProvider, SiteDataUnavailableError
from field_shift.reference.measures import MEASURE_IDS, MEASURE_NAMES

COORDINATE_DECIMALS = 6
AREA_DECIMALS = 4


class RankingInputError(ValueError):
    """The request is well formed but cannot be ranked (the route answers 422 with the message)."""


class SectionDataError(RuntimeError):
    """The data services could not give what a section needs (the route answers 502)."""

    def __init__(self, section_id: str, error: SiteDataUnavailableError) -> None:
        super().__init__(f"section {section_id} : {error}")
        self.section_id = section_id
        self.failures = error.failures


def merged_readings(*layers: Sequence[SiteReading]) -> list[SiteReading]:
    """One reading per variable: a later layer replaces the earlier ones."""
    merged: dict[str, SiteReading] = {}
    for layer in layers:
        merged.update({reading.key: reading for reading in layer})
    return list(merged.values())


class RankingService:
    """Ranks the candidate rotations of every section of a field."""

    def __init__(
        self, site_data: SiteDataProvider, measures: Sequence[Measure] | None = None
    ) -> None:
        self._site_data = site_data
        self._measures = tuple(all_measures() if measures is None else measures)

    @property
    def implemented_measures(self) -> list[str]:
        return [measure.id for measure in self._measures if measure.implemented]

    @property
    def pending_measures(self) -> list[str]:
        return [measure.id for measure in self._measures if not measure.implemented]

    def rank(self, ranking_input: RankingInput, only_measure: str | None = None) -> RotationRanking:
        """The rotations of every section, ranked.

        `only_measure` ranks on one measure alone, whatever the priorities (the `/measures/…`
        routes). Raises RankingInputError when the request cannot be ranked.
        """
        try:
            request = read_ranking_input(ranking_input)
        except ValueError as error:
            raise RankingInputError(str(error)) from error
        weights = request.weights
        if only_measure is not None:
            weights = {measure: float(measure == only_measure) for measure in MEASURE_IDS}
        sections = [
            self._rank_section(section, request, weights) for section in ranking_input.sections
        ]
        return RotationRanking(
            meta=RankingMetaOut(
                simulation_years=ranking_input.simulation_years,
                weights={measure: round(weight, 4) for measure, weight in weights.items()},
                implemented_measures=self.implemented_measures,
                pending_measures=self.pending_measures,
                rotation_count=len(request.rotations),
                rotations_generated=request.generated,
                notes=self._notes(weights),
            ),
            sections=sections,
        )

    def _rank_section(
        self,
        section: RankingSectionInput,
        request: RankingRequest,
        weights: dict[str, float],
    ) -> SectionRankingOut:
        shape = section.geometry.shape
        given = section_readings(section)
        given_keys = {reading.key for reading in given}
        needed = [key for key in SITE_VARIABLES if key not in given_keys | set(ESTIMATED_FROM)]
        try:
            read = self._site_data.site_readings(shape, needed)
        except SiteDataUnavailableError as error:
            raise SectionDataError(section.id, error) from error
        try:
            readings = with_estimates(merged_readings(read, given))
            site = site_from_readings(readings)
        except ValueError as error:  # e.g. the sand of the request + the clay of SoilGrids > 100 %
            raise RankingInputError(f"section {section.id} : {error}") from error
        lon, lat = shape.centroid
        context = SectionContext(
            section_id=section.id,
            lat=lat,
            lon=lon,
            site=site,
            simulation_months=request.simulation_months,
            area_ha=shape.area_ha,
            irrigated=section.irrigated,
        )
        ranked = rank_rotations(request.rotations, context, weights, self._measures)
        return SectionRankingOut(
            id=section.id,
            area_ha=round(shape.area_ha, AREA_DECIMALS),
            centroid=PointOut(
                lat=round(lat, COORDINATE_DECIMALS), lon=round(lon, COORDINATE_DECIMALS)
            ),
            site=site_out(readings),
            notes=site_notes(readings, site),
            rotations=[ranked_rotation_out(rotation) for rotation in ranked],
        )

    def _notes(self, weights: dict[str, float]) -> list[str]:
        """What the reader must know to read the scores."""
        notes = []
        pending = self.pending_measures
        if pending:
            names = ", ".join(MEASURE_NAMES[measure] for measure in pending)
            notes.append(
                f"Mesures pas encore calculées, laissées hors du score : {names}. Le poids des "
                "mesures disponibles est remis à l’échelle."
            )
        if not any(weights[measure] > 0 for measure in self.implemented_measures):
            notes.append(
                "Aucune mesure disponible n’a de poids : les rotations ne sont pas classées "
                "(score absent) et gardent l’ordre de la demande."
            )
        return notes

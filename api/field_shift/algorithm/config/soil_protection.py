"""Constants of the soil protection measure (erosion and infiltration), named and sourced.

Three references are used throughout:
  [RUSLE2]  USDA RUSLE Development Team, "Revised Universal Soil Loss Equation Version 2 (RUSLE2)
            Handbook", March 2001;
  [AH703]   Renard et al., "Predicting Soil Erosion by Water", USDA Agriculture Handbook 703, 1997
            (the equations of RUSLE1, which the RUSLE2 handbook refers to);
  [META]    Basche and DeLonge, "Comparing infiltration rates in soils managed with conventional
            and alternative farming methods: A meta-analysis", PLOS ONE 14(9), 2019.

The model is in SI units: soil loss in t/ha/year, erosivity R in MJ·mm/(ha·h·year), erodibility K
in t·ha·h/(ha·MJ·mm), lengths in metres, infiltration in mm/h.
"""

from __future__ import annotations

from typing import Final

# --- Rotation Protection Index (RPI) --------------------------------------------------------------

#: Intrinsic score of bare soil and fallow: the lowest of the classification matrix.
BARE_SOIL_SCORE: Final = 1.0
#: Highest intrinsic score (a perennial with massive roots, a mat of residue, a permanent canopy).
BEST_SCORE: Final = 5.0
#: RPI below this: high erosion risk, poor infiltration (degradation alert).
RPI_MODERATE_FROM: Final = 2.5
#: RPI from this: excellent protection, the soil structure regenerates.
RPI_EXCELLENT_FROM: Final = 4.0

# --- Vigour adjustment (step 3 of the pipeline) ---------------------------------------------------

#: NDVI of a dense, healthy canopy: a growing-season NDVI at or above it means full vigour.
NDVI_FULL_CANOPY: Final = 0.8
#: NDVI of bare soil: at or below it, the canopy protects nothing.
NDVI_BARE_SOIL: Final = 0.15

# --- RUSLE: cover-management factor C -------------------------------------------------------------

#: Effectiveness `b` of surface cover in `exp(-b·M)`, M in percent. [RUSLE2] gives about 0.035
#: for conventional tillage (0.05 for long-term no-till, where cover also raises infiltration).
SURFACE_COVER_EFFECTIVENESS: Final = 0.035
#: Ground cover (%) left by the residue of a crop, by residue score 1..5 of the matrix.
RESIDUE_COVER_PCT_BY_SCORE: Final[dict[int, float]] = {1: 10, 2: 25, 3: 45, 4: 65, 5: 90}
#: After a harvest the residue stays on the soil and decays: months for its cover to halve.
#: ([RUSLE2] computes the decay from monthly temperature and rain; one mean value is used here.)
RESIDUE_HALF_LIFE_MONTHS: Final = 6.0
#: Share of the soil under the canopy, averaged over the season (emergence to harvest).
CANOPY_COVER_ANNUAL: Final = 0.6
#: The same for perennials and cover crops, which close their canopy and keep it.
CANOPY_COVER_DENSE: Final = 0.9
#: Effective height (m) from which the drops fall off the canopy ([AH703], canopy subfactor
#: `1 - Fc·exp(-0.1·H)` with H in feet).
CANOPY_FALL_HEIGHT_M: Final = 0.5
CANOPY_HEIGHT_DECAY_PER_FT: Final = 0.1
FEET_PER_METRE: Final = 3.28084
#: A soil left undisturbed consolidates: fully consolidated, it loses about 45 % of what it loses
#: right after tillage, and this takes about seven years ([RUSLE2], "Prior Land Use").
CONSOLIDATED_SOIL_LOSS_RATIO: Final = 0.45
CONSOLIDATION_YEARS: Final = 7.0

# --- RUSLE: topography LS ([AH703], also summarised in [RUSLE2]) ----------------------------------

#: Length of the unit plot: 72.6 ft.
UNIT_PLOT_LENGTH_M: Final = 22.13
#: The slope steepness factor S changes of equation at 9 % (the unit plot).
STEEPNESS_BREAK_PCT: Final = 9.0
#: Slope lengths beyond 1000 ft must not be used: flow concentrates before ([RUSLE2]).
MAX_SLOPE_LENGTH_M: Final = 304.8
#: The steepest slope RUSLE2 accepts.
MAX_SLOPE_PCT: Final = 100.0
#: "Slope lengths on many landscapes generally are less than 200 ft" ([RUSLE2]): 60 m by default.
DEFAULT_SLOPE_LENGTH_M: Final = 60.0

# --- RUSLE: erosivity R and erodibility K ---------------------------------------------------------

#: Annual rain (mm) where the erosivity estimate changes of equation (Renard and Freimund, 1994).
EROSIVITY_RAIN_BREAK_MM: Final = 850.0
#: K in US customary units × this = K in SI units ([AH703], appendix A).
K_US_TO_SI: Final = 0.1317
#: Organic matter (%) = organic carbon (%) × this (Van Bemmelen factor).
ORGANIC_MATTER_PER_CARBON: Final = 1.724
#: Soil loss tolerance T: 5 tons/acre/year, the usual value of NRCS for deep soils ([RUSLE2]:
#: "typical values of T range from 3 to 5 tons/acre/year"), in t/ha/year.
SOIL_LOSS_TOLERANCE_T_HA_YEAR: Final = 11.2

# --- Infiltration ([META]) ------------------------------------------------------------------------

#: Mean increase of the infiltration rate with perennials, against annual crops: +59.2 %.
PERENNIAL_INFILTRATION_GAIN: Final = 0.592
#: Mean increase of the infiltration rate with cover crops, against bare soil: +34.8 %.
COVER_CROP_INFILTRATION_GAIN: Final = 0.348
#: A saturated soil (SMAP) takes almost no more water: share of the infiltration lost at
#: saturation.
SATURATION_INFILTRATION_LOSS: Final = 0.9
#: Rain intensity (mm/h) of the storm the infiltration is compared with, when GPM IMERG does not
#: give one: a heavy shower.
DEFAULT_STORM_INTENSITY_MM_H: Final = 25.0

# --- Score of the measure -------------------------------------------------------------------------

#: The soil protection score (0 to 1) mixes the three results of the pipeline with these shares.
SCORE_SHARE_RPI: Final = 0.3
SCORE_SHARE_EROSION: Final = 0.4
SCORE_SHARE_INFILTRATION: Final = 0.3

# --- Site: values used when neither the section nor a data source gives them ----------------------

#: A gentle slope (%), the middle of the range where RUSLE2 "works best" starts at 3 %.
DEFAULT_SLOPE_PCT: Final = 3.0
#: Texture of a loam (%); silt is what remains.
DEFAULT_SAND_PCT: Final = 40.0
DEFAULT_CLAY_PCT: Final = 20.0
DEFAULT_ORGANIC_MATTER_PCT: Final = 3.0
#: Saturated hydraulic conductivity of a loam (mm/h).
DEFAULT_KSAT_MM_H: Final = 10.0
#: Annual rain (mm) of southern Quebec, where the demo farm is.
DEFAULT_ANNUAL_RAIN_MM: Final = 1000.0

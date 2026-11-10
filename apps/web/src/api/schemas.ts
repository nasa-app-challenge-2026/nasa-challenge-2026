/**
 * Runtime-validated contracts of the backend API (apps/api/src/fieldshift/api/schemas).
 * Only the fields used by the interface are declared; unknown fields are dropped.
 */
import { z } from "zod";

const num = z.number();
const nullableNum = num.nullable();

export const basisSchema = z.object({
  source_ids: z.array(z.string()),
  confidence: z.enum(["documented", "provisional"]),
  note_fr: z.string(),
});

export const cropSchema = z.object({
  id: z.string(),
  name_fr: z.string(),
  category: z.enum(["annual", "perennial_forage", "perennial_woody"]),
  heat_requirement: z
    .object({ unit: z.string(), minimum: num, maximum: num, basis: basisSchema })
    .nullable(),
  frost_tolerance: z
    .object({ damage_threshold_c: num, inclusive: z.boolean(), basis: basisSchema })
    .nullable(),
  water_need: z.object({ minimum_mm: num, maximum_mm: num, basis: basisSchema }).nullable(),
});

export const observationSchema = z.object({
  text: z.string(),
  topic: z.enum(["frost", "harvest_weather", "water", "weeds", "market", "other"]),
  year: z.number().int().nullable(),
  crop_id: z.string().nullable(),
});

export const prioritiesSchema = z.object({
  climate_resilience: z.number().int().min(0).max(3),
  soil_health: z.number().int().min(0).max(3),
  water_conservation: z.number().int().min(0).max(3),
  potential_income: z.number().int().min(0).max(3),
});

export const farmProfileSchema = z.object({
  name: z.string(),
  location: z.object({
    latitude: num,
    longitude: num,
    precision: z.enum(["exact", "approximate"]),
  }),
  current_rotation: z.object({ name_fr: z.string(), crop_ids: z.array(z.string()) }),
  priorities: prioritiesSchema,
  soil_texture: z.string().nullable(),
  soil_information_source: z.string().nullable(),
  irrigation_available: z.boolean().nullable(),
  excluded_crop_ids: z.array(z.string()),
  observations: z.array(observationSchema),
});

export const demoFarmSchema = z.object({
  id: z.string(),
  description_fr: z.string(),
  provenance_fr: z.string(),
  profile: farmProfileSchema,
});

export const referenceSchema = z.object({
  id: z.string(),
  citation: z.string(),
  url: z.string().nullable(),
  accessed: z.string().nullable(),
  terms_fr: z.string(),
});

const provenanceSchema = z.object({
  provider: z.string(),
  product: z.string(),
  api_version: z.string().nullable(),
  period_start: z.string(),
  period_end: z.string(),
  retrieved_at: z.string(),
  origin: z.enum(["live_api", "local_cache", "verified_snapshot"]),
  nature: z.string(),
  spatial_resolution: z.string(),
  time_standard: z.string(),
  grid_cell: z.object({
    cell_id: z.string(),
    latitude_min: num,
    latitude_max: num,
    longitude_min: num,
    longitude_max: num,
  }),
  grid_cell_elevation_m: nullableNum,
  parameters: z.array(z.object({ code: z.string(), name: z.string(), unit: z.string() })),
  citation: z.string(),
  license: z.string(),
  content_sha256: z.string(),
});

const qualitySchema = z.object({
  level: z.enum(["complete", "partial"]),
  years_excluded: z.array(z.object({ year: num, missing_days: num })),
  warnings: z.array(z.object({ code: z.string(), message_fr: z.string() })),
});

const periodSchema = z.object({ first_year: num, last_year: num, years_analysed: num });

export const indicatorSchema = z.object({
  id: z.string(),
  group: z.string(),
  kind: z.enum(["quantity", "day_of_year"]),
  label_fr: z.string(),
  unit: z.string(),
  definition_fr: z.string(),
  source_ids: z.array(z.string()),
  values: z.array(z.object({ year: num, value: nullableNum })),
  summary: z
    .object({
      median: num,
      p20: num,
      p80: num,
      minimum: num,
      maximum: num,
      trend: z
        .object({ slope_per_decade: num, p_value: num, is_significant: z.boolean() })
        .nullable(),
    })
    .nullable(),
});

export const climateAnalysisSchema = z.object({
  period: periodSchema,
  provenance: provenanceSchema,
  quality: qualitySchema,
  indicators: z.array(indicatorSchema),
  monthly_normals: z.array(
    z.object({
      month: num,
      t_mean_c: num,
      t_max_mean_c: num,
      t_min_mean_c: num,
      precipitation_mm: num,
    }),
  ),
  observation_checks: z.array(
    z.object({
      observation: observationSchema,
      status: z.string(),
      positions: z.array(
        z.object({
          indicator_id: z.string(),
          value: nullableNum,
          median: nullableNum,
          years_higher: num,
          years_lower: num,
          years_compared: num,
        }),
      ),
    }),
  ),
  observation_scale_note_fr: z.string(),
});

const statementSchema = z.object({
  kind: z.enum(["benefit", "tradeoff", "uncertainty", "to_validate"]),
  text_fr: z.string(),
  source_ids: z.array(z.string()),
});

const evaluationSchema = z.object({
  rotation: z.object({ id: z.string(), name_fr: z.string(), crop_ids: z.array(z.string()) }),
  admissible: z.boolean(),
  blocking_reasons_fr: z.array(z.string()),
  criteria: z.array(
    z.object({ criterion: z.string(), label_fr: z.string(), score: nullableNum, coverage: num }),
  ),
  stress_test: z.object({
    years: num,
    mean_exposed_share: num,
    years_with_exposure: num,
    worst_years: z.array(num),
    yearly: z.array(
      z.object({ year: num, exposed_share: num, exposed_crop_ids: z.array(z.string()) }),
    ),
    unevaluated_hazards: z.array(z.object({ crop_id: z.string(), description_fr: z.string() })),
  }),
});

export const comparisonSchema = z.object({
  period: periodSchema,
  provenance: provenanceSchema,
  quality: qualitySchema,
  criteria_status: z.array(
    z.object({
      criterion: z.string(),
      label_fr: z.string(),
      used_in_ranking: z.boolean(),
      reason_fr: z.string(),
    }),
  ),
  strategies: z.array(
    z.object({
      role: z.enum(["current", "resilience_and_soil", "farmer_priorities", "user_selected"]),
      evaluation: evaluationSchema,
      score_farmer_priorities: nullableNum,
      explanation: z.object({
        why_fr: z.string(),
        statements: z.array(statementSchema),
        source_ids: z.array(z.string()),
      }),
    }),
  ),
  considered: z.array(
    z.object({
      evaluation: evaluationSchema,
      score_farmer_priorities: nullableNum,
      selected_as: z.string().nullable(),
    }),
  ),
  crop_records: z.array(
    z.object({
      crop_id: z.string(),
      years: num,
      heat_evaluated: z.boolean(),
      frost_evaluated: z.boolean(),
      heat_shortfall_years: num,
      heat_tight_years: num,
      frost_exposed_years: num,
    }),
  ),
  notes_fr: z.array(z.string()),
  method_limits_fr: z.array(z.string()),
});

export const problemSchema = z.object({ code: z.string(), detail: z.string() });

export type Crop = z.infer<typeof cropSchema>;
export type FarmProfile = z.infer<typeof farmProfileSchema>;
export type DemoFarm = z.infer<typeof demoFarmSchema>;
export type Reference = z.infer<typeof referenceSchema>;
export type Indicator = z.infer<typeof indicatorSchema>;
export type ClimateAnalysis = z.infer<typeof climateAnalysisSchema>;
export type Comparison = z.infer<typeof comparisonSchema>;
export type Strategy = Comparison["strategies"][number];

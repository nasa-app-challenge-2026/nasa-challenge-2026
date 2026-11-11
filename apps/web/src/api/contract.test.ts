/**
 * Contract test: real API responses (generated from the versioned NASA snapshot by
 * scripts/export_api_fixtures.py) must satisfy the frontend's runtime schemas.
 */
import { z } from "zod";
import climate from "./__fixtures__/climate-analyze.sacre-coeur.json";
import comparison from "./__fixtures__/rotations-compare.sacre-coeur.json";
import demoFarms from "./__fixtures__/demo-farms.json";
import { climateAnalysisSchema, comparisonSchema, demoFarmSchema } from "./schemas";
import { formatDayOfYear, formatPercent } from "../utils/format";

test("backend responses satisfy the frontend contracts", () => {
  expect(z.array(demoFarmSchema).parse(demoFarms)[0]?.id).toBe("sacre-coeur");
  expect(climateAnalysisSchema.parse(climate).period.years_analysed).toBe(45);
  expect(comparisonSchema.parse(comparison).strategies.map((s) => s.role)).toEqual([
    "current",
    "resilience_and_soil",
    "farmer_priorities",
  ]);
});

test("formatting helpers", () => {
  expect(formatPercent(0.625)).toBe("63 %");
  expect(formatDayOfYear(1)).toBe("1 janvier");
  expect(formatPercent(null)).toBe("—");
});

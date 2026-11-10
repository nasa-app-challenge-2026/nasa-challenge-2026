import { z } from "zod";
import {
  climateAnalysisSchema,
  comparisonSchema,
  cropSchema,
  demoFarmSchema,
  problemSchema,
  referenceSchema,
  type FarmProfile,
} from "./schemas";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Le serveur d'analyse est injoignable. Est-il démarré ?", "network");
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const problem = problemSchema.safeParse(payload);
    throw new ApiError(
      problem.success ? problem.data.detail : `Erreur HTTP ${response.status}`,
      problem.success ? problem.data.code : "http",
    );
  }
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiError("Réponse du serveur inattendue (contrat d'API non respecté).", "contract");
  }
  return parsed.data;
}

export const api = {
  crops: () => request("/crops", z.array(cropSchema)),
  demoFarms: () => request("/demo-farms", z.array(demoFarmSchema)),
  sources: () => request("/sources", z.array(referenceSchema)),
  analyzeClimate: (farm: FarmProfile) =>
    request("/climate/analyze", climateAnalysisSchema, {
      location: farm.location,
      observations: farm.observations,
    }),
  compareRotations: (farm: FarmProfile, selected?: string[]) =>
    request("/rotations/compare", comparisonSchema, {
      farm,
      selected_template_ids: selected?.length ? selected : null,
    }),
};

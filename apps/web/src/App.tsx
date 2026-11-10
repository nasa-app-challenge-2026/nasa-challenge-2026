import { useEffect, useState } from "react";
import { ApiError, api } from "./api/client";
import type {
  ClimateAnalysis,
  Comparison,
  Crop,
  DemoFarm,
  FarmProfile,
  Reference,
} from "./api/schemas";
import { Status } from "./components/Status";
import { ClimateDashboard } from "./features/climate-dashboard/ClimateDashboard";
import { DataSources } from "./features/data-sources/DataSources";
import { FarmProfileForm } from "./features/farm-profile/FarmProfileForm";
import { HistoricalStressTest } from "./features/historical-simulation/HistoricalStressTest";
import { RotationComparison } from "./features/rotation-comparison/RotationComparison";

type Results = { climate: ClimateAnalysis; comparison: Comparison };

export function App() {
  const [crops, setCrops] = useState<Crop[]>([]);
  const [references, setReferences] = useState<Reference[]>([]);
  const [demo, setDemo] = useState<DemoFarm | null>(null);
  const [profile, setProfile] = useState<FarmProfile | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.crops(), api.sources(), api.demoFarms()])
      .then(([c, r, demos]) => {
        setCrops(c);
        setReferences(r);
        setDemo(demos[0] ?? null);
        setProfile(demos[0]?.profile ?? null);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Erreur inattendue."));
  }, []);

  async function analyze() {
    if (!profile) return;
    setBusy(true);
    setError(null);
    try {
      const [climate, comparison] = await Promise.all([
        api.analyzeClimate(profile),
        api.compareRotations(profile),
      ]);
      setResults({ climate, comparison });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="header">
        <h1>Field Shift — rotations et climat</h1>
        <p>
          Outil d'exploration fondé sur les données climatiques de la NASA. Il ne remplace pas un
          agronome et ne garantit aucun rendement.
        </p>
      </header>
      <main className="layout">
        {error && <Status kind="error">{error}</Status>}
        {!profile && !error && <Status kind="loading">Chargement du référentiel…</Status>}
        {demo && (
          <Status kind="info">
            Profil de démonstration : {demo.description_fr} {demo.provenance_fr}
          </Status>
        )}
        {profile && (
          <FarmProfileForm
            profile={profile}
            crops={crops}
            cell={results?.climate.provenance.grid_cell}
            busy={busy}
            onChange={(next) => setProfile(next)}
            onSubmit={() => void analyze()}
          />
        )}
        {busy && (
          <Status kind="loading">Récupération des données NASA et calcul sur ~45 ans…</Status>
        )}
        {results && (
          <>
            <ClimateDashboard analysis={results.climate} />
            <RotationComparison comparison={results.comparison} crops={crops} />
            <HistoricalStressTest comparison={results.comparison} crops={crops} />
            <DataSources comparison={results.comparison} references={references} />
          </>
        )}
        {profile && !results && !busy && (
          <Status kind="empty">Lancez l'analyse pour voir le climat et les rotations.</Status>
        )}
      </main>
    </>
  );
}

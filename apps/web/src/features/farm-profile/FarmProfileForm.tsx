import type { Crop, FarmProfile } from "../../api/schemas";
import { FarmMap } from "./FarmMap";

type Props = {
  profile: FarmProfile;
  crops: Crop[];
  cell?: Parameters<typeof FarmMap>[0]["cell"];
  busy: boolean;
  onChange: (profile: FarmProfile) => void;
  onSubmit: () => void;
};

const PRIORITIES = [
  ["climate_resilience", "Résilience climatique"],
  ["soil_health", "Santé du sol"],
  ["water_conservation", "Conservation de l'eau"],
  ["potential_income", "Revenu potentiel"],
] as const;
const LEVELS = ["Ignorer", "Un peu", "Important", "Essentiel"];
const SOILS: [string, string][] = [
  ["", "Inconnu"],
  ["sand", "Sable"],
  ["sandy_loam", "Loam sableux"],
  ["loam", "Loam"],
  ["silt_loam", "Loam limoneux"],
  ["clay_loam", "Loam argileux"],
  ["clay", "Argile"],
  ["organic", "Organique"],
];

export function FarmProfileForm({ profile, crops, cell, busy, onChange, onSubmit }: Props) {
  const rotationCrops = crops.filter((crop) => crop.category !== "perennial_woody");
  const rotation = profile.current_rotation.crop_ids;
  const setRotation = (crop_ids: string[]) =>
    onChange({ ...profile, current_rotation: { ...profile.current_rotation, crop_ids } });

  return (
    <form
      className="panel"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <h2>1. Votre ferme</h2>
      <FarmMap
        latitude={profile.location.latitude}
        longitude={profile.location.longitude}
        cell={cell}
        onPick={(latitude, longitude) =>
          onChange({ ...profile, location: { latitude, longitude, precision: "exact" } })
        }
      />
      <p className="hint">
        Position : {profile.location.latitude.toFixed(3)}, {profile.location.longitude.toFixed(3)} (
        {profile.location.precision === "approximate" ? "approximative" : "placée sur la carte"}).
        Le cadre bleu montre la cellule NASA réellement analysée.
      </p>

      <fieldset>
        <legend>Rotation actuelle (une culture par année)</legend>
        <ol className="rotation">
          {rotation.map((cropId, index) => (
            <li key={index}>
              <label>
                Année {index + 1}
                <select
                  value={cropId}
                  onChange={(event) =>
                    setRotation(rotation.map((id, i) => (i === index ? event.target.value : id)))
                  }
                >
                  {rotationCrops.map((crop) => (
                    <option key={crop.id} value={crop.id}>
                      {crop.name_fr}
                    </option>
                  ))}
                </select>
              </label>
              {rotation.length > 1 && (
                <button
                  type="button"
                  onClick={() => setRotation(rotation.filter((_, i) => i !== index))}
                  aria-label={`Retirer l'année ${index + 1}`}
                >
                  ✕
                </button>
              )}
            </li>
          ))}
        </ol>
        {rotation.length < 8 && (
          <button
            type="button"
            onClick={() => setRotation([...rotation, rotationCrops[0]?.id ?? "oat"])}
          >
            + Ajouter une année
          </button>
        )}
      </fieldset>

      <fieldset className="grid-2">
        <legend>Sol et eau (laisser « Inconnu » si vous ne savez pas)</legend>
        <label>
          Texture du sol
          <select
            value={profile.soil_texture ?? ""}
            onChange={(event) =>
              onChange({
                ...profile,
                soil_texture: event.target.value || null,
                soil_information_source: event.target.value ? "declared_by_farmer" : null,
              })
            }
          >
            {SOILS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Irrigation possible
          <select
            value={
              profile.irrigation_available === null ? "" : String(profile.irrigation_available)
            }
            onChange={(event) =>
              onChange({
                ...profile,
                irrigation_available:
                  event.target.value === "" ? null : event.target.value === "true",
              })
            }
          >
            <option value="">Inconnu</option>
            <option value="true">Oui</option>
            <option value="false">Non</option>
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Vos priorités</legend>
        {PRIORITIES.map(([key, label]) => (
          <label key={key} className="priority">
            <span>{label}</span>
            <input
              type="range"
              min={0}
              max={3}
              step={1}
              value={profile.priorities[key]}
              onChange={(event) =>
                onChange({
                  ...profile,
                  priorities: { ...profile.priorities, [key]: Number(event.target.value) },
                })
              }
            />
            <output>{LEVELS[profile.priorities[key]]}</output>
          </label>
        ))}
      </fieldset>

      {profile.observations.length > 0 && (
        <details>
          <summary>Observations déclarées ({profile.observations.length})</summary>
          <ul>
            {profile.observations.map((o, i) => (
              <li key={i}>
                {o.text}
                {o.year ? ` (${o.year})` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}

      <button type="submit" className="primary" disabled={busy}>
        {busy ? "Analyse en cours…" : "Analyser le climat et comparer les rotations"}
      </button>
    </form>
  );
}

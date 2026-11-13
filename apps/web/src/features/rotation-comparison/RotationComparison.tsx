import type { Comparison, Crop, Strategy } from "../../api/schemas";
import { formatPercent } from "../../utils/format";

const ROLE_LABELS: Record<Strategy["role"], string> = {
  current: "Rotation actuelle",
  resilience_and_soil: "Alternative : résilience et santé du sol",
  farmer_priorities: "Alternative : selon vos priorités",
  user_selected: "Alternative choisie",
};
const KIND_LABELS = {
  benefit: "Bénéfices",
  tradeoff: "Risques et compromis",
  uncertainty: "Incertitudes",
  to_validate: "À valider localement",
} as const;

function StrategyCard({
  strategy,
  cropName,
}: {
  strategy: Strategy;
  cropName: (id: string) => string;
}) {
  const e = strategy.evaluation;
  return (
    <article className="card strategy">
      <p className="role">{ROLE_LABELS[strategy.role]}</p>
      <h3>{e.rotation.name_fr}</h3>
      <ol className="chips">
        {e.rotation.crop_ids.map((id, i) => (
          <li key={i}>{cropName(id)}</li>
        ))}
      </ol>
      <p>{strategy.explanation.why_fr}</p>
      <dl className="scores">
        {e.criteria.map((c) => (
          <div key={c.criterion}>
            <dt>{c.label_fr}</dt>
            <dd>
              {c.score === null ? (
                <span className="muted">non évalué</span>
              ) : (
                <>
                  <meter min={0} max={1} value={c.score} aria-label={c.label_fr} />{" "}
                  {formatPercent(c.score)}
                </>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <p className="hint">
        Champs touchés par une contrainte documentée :{" "}
        {formatPercent(e.stress_test.mean_exposed_share)} en moyenne par an ; au moins un champ
        touché {e.stress_test.years_with_exposure} année(s) sur {e.stress_test.years}.
      </p>
      {(Object.keys(KIND_LABELS) as (keyof typeof KIND_LABELS)[]).map((kind) => {
        const items = strategy.explanation.statements.filter((s) => s.kind === kind);
        return (
          items.length > 0 && (
            <div key={kind} className={`statements statements--${kind}`}>
              <h4>{KIND_LABELS[kind]}</h4>
              <ul>
                {items.map((s, i) => (
                  <li key={i}>
                    {s.text_fr}
                    {s.source_ids.length > 0 && (
                      <span className="src"> [{s.source_ids.join(", ")}]</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )
        );
      })}
    </article>
  );
}

export function RotationComparison({
  comparison,
  crops,
}: {
  comparison: Comparison;
  crops: Crop[];
}) {
  const names = new Map(crops.map((c) => [c.id, c.name_fr]));
  const cropName = (id: string) => names.get(id) ?? id;
  return (
    <section className="panel" aria-labelledby="comparison-title">
      <h2 id="comparison-title">3. Trois stratégies comparées</h2>
      <ul className="criteria-status">
        {comparison.criteria_status.map((c) => (
          <li key={c.criterion}>
            <strong>{c.label_fr}</strong> :{" "}
            {c.used_in_ranking ? "utilisé dans le classement" : c.reason_fr}
          </li>
        ))}
      </ul>
      {comparison.notes_fr.map((n) => (
        <p key={n} className="status status--info">
          {n}
        </p>
      ))}
      <div className="strategies">
        {comparison.strategies.map((s) => (
          <StrategyCard key={s.evaluation.rotation.id} strategy={s} cropName={cropName} />
        ))}
      </div>
      <details>
        <summary>Toutes les rotations évaluées ({comparison.considered.length})</summary>
        <table>
          <thead>
            <tr>
              <th>Rotation</th>
              <th>Admissible</th>
              <th>Score (vos priorités)</th>
              <th>Raison</th>
            </tr>
          </thead>
          <tbody>
            {comparison.considered.map((c) => (
              <tr key={c.evaluation.rotation.id}>
                <td>{c.evaluation.rotation.name_fr}</td>
                <td>{c.evaluation.admissible ? "oui" : "non"}</td>
                <td>{formatPercent(c.score_farmer_priorities)}</td>
                <td>
                  {c.evaluation.blocking_reasons_fr.join(" ") ||
                    (c.selected_as ? "retenue ci-dessus" : "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

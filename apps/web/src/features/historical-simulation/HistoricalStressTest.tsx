import type { Comparison, Crop } from "../../api/schemas";

/** Years × strategies grid: share of the rotation's fields meeting a documented constraint. */
export function HistoricalStressTest({
  comparison,
  crops,
}: {
  comparison: Comparison;
  crops: Crop[];
}) {
  const names = new Map(crops.map((c) => [c.id, c.name_fr]));
  const years = comparison.strategies[0]?.evaluation.stress_test.yearly.map((y) => y.year) ?? [];
  return (
    <section className="panel" aria-labelledby="stress-title">
      <h2 id="stress-title">4. Stress test sur {years.length} années passées</h2>
      <p className="hint">
        Chaque case : part des champs de la rotation dont la culture aurait manqué de chaleur pour
        mûrir ou subi un gel au seuil de dommage documenté, cette année-là. Ce n'est pas un
        rendement.
      </p>
      <div
        className="heatmap"
        style={{
          gridTemplateColumns: `minmax(9rem, 14rem) repeat(${years.length}, minmax(0.6rem, 1fr))`,
        }}
      >
        {comparison.strategies.map((s) => (
          <div key={s.evaluation.rotation.id} className="heatmap-row" role="row">
            <span className="heatmap-label">{s.evaluation.rotation.name_fr}</span>
            {s.evaluation.stress_test.yearly.map((y) => (
              <span
                key={y.year}
                className="heatmap-cell"
                style={{
                  background:
                    y.exposed_share === 0
                      ? "#e8f0e8"
                      : `rgba(185, 28, 28, ${0.25 + 0.75 * y.exposed_share})`,
                }}
                title={`${y.year} : ${Math.round(y.exposed_share * 100)} % des champs${y.exposed_crop_ids.length ? ` (${y.exposed_crop_ids.map((id) => names.get(id) ?? id).join(", ")})` : ""}`}
              />
            ))}
          </div>
        ))}
        <div className="heatmap-row heatmap-axis" aria-hidden>
          <span />
          {years.map((y) => (
            <span key={y}>{y % 10 === 0 ? y : ""}</span>
          ))}
        </div>
      </div>
      <h3>Par culture</h3>
      <table>
        <thead>
          <tr>
            <th>Culture</th>
            <th>Manque de chaleur</th>
            <th>Chaleur juste suffisante</th>
            <th>Gel dommageable</th>
          </tr>
        </thead>
        <tbody>
          {comparison.crop_records.map((r) => (
            <tr key={r.crop_id}>
              <td>{names.get(r.crop_id) ?? r.crop_id}</td>
              <td>
                {r.heat_evaluated ? `${r.heat_shortfall_years} / ${r.years} ans` : "non évalué"}
              </td>
              <td>{r.heat_evaluated ? `${r.heat_tight_years} / ${r.years} ans` : "—"}</td>
              <td>
                {r.frost_evaluated ? `${r.frost_exposed_years} / ${r.years} ans` : "non documenté"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

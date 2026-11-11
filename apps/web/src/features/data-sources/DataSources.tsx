import type { Comparison, Reference } from "../../api/schemas";

export function DataSources({
  comparison,
  references,
}: {
  comparison: Comparison;
  references: Reference[];
}) {
  const p = comparison.provenance;
  return (
    <section className="panel" aria-labelledby="sources-title">
      <h2 id="sources-title">5. Données, sources et limites</h2>
      <dl className="provenance">
        <dt>Source</dt>
        <dd>{p.provider}</dd>
        <dt>Produit</dt>
        <dd>
          {p.product} ({p.api_version ?? "version inconnue"})
        </dd>
        <dt>Période</dt>
        <dd>
          {p.period_start} au {p.period_end} ({p.time_standard})
        </dd>
        <dt>Résolution</dt>
        <dd>
          {p.spatial_resolution} ; cellule {p.grid_cell.cell_id}, altitude moyenne{" "}
          {p.grid_cell_elevation_m ?? "?"} m
        </dd>
        <dt>Variables</dt>
        <dd>{p.parameters.map((x) => `${x.code} (${x.unit})`).join(", ")}</dd>
        <dt>Obtenu le</dt>
        <dd>
          {new Date(p.retrieved_at).toLocaleString("fr-CA")} ; SHA-256{" "}
          {p.content_sha256.slice(0, 12)}…
        </dd>
        <dt>Licence</dt>
        <dd>{p.license}</dd>
        <dt>Citation</dt>
        <dd>{p.citation}</dd>
      </dl>
      <h3>Limites de la méthode</h3>
      <ul>
        {comparison.method_limits_fr.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
      <h3>Références</h3>
      <ol className="references">
        {references.map((r) => (
          <li key={r.id} id={`ref-${r.id}`}>
            <code>{r.id}</code> — {r.citation}{" "}
            {r.url && (
              <a href={r.url} target="_blank" rel="noreferrer">
                lien
              </a>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

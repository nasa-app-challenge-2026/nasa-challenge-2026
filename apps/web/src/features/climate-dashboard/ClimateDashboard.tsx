import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ClimateAnalysis, Indicator } from "../../api/schemas";
import { formatDayOfYear, formatNumber } from "../../utils/format";

const KEY_INDICATORS = [
  "crop_heat_units",
  "gdd_base0",
  "frost_free_season_days",
  "growing_season_length_days",
  "last_spring_frost_doy",
  "first_fall_frost_doy",
  "precipitation_growing_season_mm",
  "haymaking_days_june_july",
];

const show = (indicator: Indicator, value: number | null | undefined) =>
  indicator.kind === "day_of_year"
    ? formatDayOfYear(value)
    : `${formatNumber(value)} ${indicator.unit}`;

function KeyFigure({ indicator }: { indicator: Indicator }) {
  const s = indicator.summary;
  return (
    <div className="card figure" title={indicator.definition_fr}>
      <h3>{indicator.label_fr}</h3>
      <p className="big">{show(indicator, s?.median)}</p>
      <p className="hint">
        médiane · 8 ans sur 10 entre {show(indicator, s?.p20)} et {show(indicator, s?.p80)}
      </p>
      {s?.trend?.is_significant && (
        <p className="trend">
          Tendance : {s.trend.slope_per_decade > 0 ? "+" : ""}
          {formatNumber(s.trend.slope_per_decade)} par décennie (Mann-Kendall p ={" "}
          {s.trend.p_value.toFixed(3)})
        </p>
      )}
    </div>
  );
}

export function ClimateDashboard({ analysis }: { analysis: ClimateAnalysis }) {
  const byId = new Map(analysis.indicators.map((i) => [i.id, i]));
  const [selected, setSelected] = useState("crop_heat_units");
  const indicator = byId.get(selected) ?? analysis.indicators[0];
  const p = analysis.provenance;

  return (
    <section className="panel" aria-labelledby="climate-title">
      <h2 id="climate-title">
        2. Climat observé ({analysis.period.first_year}–{analysis.period.last_year})
      </h2>
      <p className="badge-row">
        <span className="badge">
          {p.origin === "live_api"
            ? "NASA POWER, en direct"
            : p.origin === "local_cache"
              ? "NASA POWER, cache local"
              : "NASA POWER, instantané vérifié"}
        </span>
        <span className="badge">Réanalyse MERRA-2, pas une mesure à la ferme</span>
        <span className="badge">{analysis.period.years_analysed} années complètes</span>
      </p>
      <ul className="warnings">
        {analysis.quality.warnings.map((w) => (
          <li key={w.code}>{w.message_fr}</li>
        ))}
      </ul>

      <div className="figures">
        {KEY_INDICATORS.map((id) => byId.get(id))
          .filter((i) => i !== undefined)
          .map((i) => (
            <KeyFigure key={i.id} indicator={i} />
          ))}
      </div>

      {indicator && (
        <div className="chart-block">
          <label>
            Indicateur année par année :{" "}
            <select value={indicator.id} onChange={(e) => setSelected(e.target.value)}>
              {analysis.indicators.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.label_fr}
                </option>
              ))}
            </select>
          </label>
          <p className="hint">{indicator.definition_fr}</p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={indicator.values} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} />
              <YAxis
                tick={{ fontSize: 12 }}
                width={56}
                tickFormatter={(v: number) =>
                  indicator.kind === "day_of_year" ? formatDayOfYear(v) : formatNumber(v)
                }
              />
              <Tooltip
                formatter={(v) => [show(indicator, Number(v)), indicator.label_fr]}
                labelFormatter={(y) => `Année ${y}`}
              />
              {indicator.summary && (
                <ReferenceLine
                  y={indicator.summary.median}
                  stroke="#6b7280"
                  strokeDasharray="4 4"
                  label={{ value: "médiane", fontSize: 11, position: "insideTopLeft" }}
                />
              )}
              <Line
                type="monotone"
                dataKey="value"
                stroke="#1d4ed8"
                strokeWidth={2}
                dot={{ r: 2 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {analysis.observation_checks.some((c) => c.status === "compared") && (
        <div>
          <h3>Vos observations face aux données</h3>
          {analysis.observation_checks
            .filter((c) => c.status === "compared")
            .map((check, i) => (
              <div key={i} className="card">
                <p>
                  <strong>« {check.observation.text} »</strong>
                </p>
                <ul>
                  {check.positions.map((pos) => {
                    const ind = byId.get(pos.indicator_id);
                    return (
                      ind && (
                        <li key={pos.indicator_id}>
                          {ind.label_fr} en {check.observation.year} : {show(ind, pos.value)}{" "}
                          (médiane {show(ind, pos.median)} ; {pos.years_higher} année(s) plus
                          élevée(s) sur {pos.years_compared})
                        </li>
                      )
                    );
                  })}
                </ul>
                <p className="hint">{analysis.observation_scale_note_fr}</p>
              </div>
            ))}
        </div>
      )}
    </section>
  );
}

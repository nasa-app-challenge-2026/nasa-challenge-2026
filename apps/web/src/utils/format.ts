const numberFormat = new Intl.NumberFormat("fr-CA", { maximumFractionDigits: 0 });

export const formatNumber = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : numberFormat.format(value);

export const formatPercent = (fraction: number | null | undefined): string =>
  fraction === null || fraction === undefined ? "—" : `${Math.round(fraction * 100)} %`;

/** Day of year (1 = 1 January) as a date label in a non-leap year, e.g. "14 mai". */
export function formatDayOfYear(day: number | null | undefined): string {
  if (day === null || day === undefined) return "—";
  const date = new Date(Date.UTC(2023, 0, Math.round(day)));
  return date.toLocaleDateString("fr-CA", { day: "numeric", month: "long", timeZone: "UTC" });
}

/**
 * Current weather and 7-day forecast at the farm, from Open-Meteo (free, no
 * key, fair use). Not NASA data: it is the "today" complement to the 10-year
 * satellite averages of "Mon champ".
 */
const BASE = 'https://api.open-meteo.com/v1/forecast';

/** WMO weather codes → French label + icon id (see frontend/ui/weatherWidget.js). */
const WMO = [
  [[0], 'Ciel dégagé', 'sun'],
  [[1], 'Plutôt dégagé', 'sun'],
  [[2], 'Partiellement nuageux', 'cloud-sun'],
  [[3], 'Couvert', 'cloud'],
  [[45, 48], 'Brouillard', 'fog'],
  [[51, 53, 55, 56, 57], 'Bruine', 'drizzle'],
  [[61, 63, 65, 66, 67], 'Pluie', 'rain'],
  [[71, 73, 75, 77], 'Neige', 'snow'],
  [[80, 81, 82], 'Averses', 'rain'],
  [[85, 86], 'Averses de neige', 'snow'],
  [[95, 96, 99], 'Orage', 'storm'],
];

export function describeWmo(code) {
  const row = WMO.find(([codes]) => codes.includes(Number(code)));
  return row ? { label: row[1], icon: row[2] } : { label: 'Météo inconnue', icon: 'cloud' };
}

/** Cache key: the forecast does not change within ~1 km. */
export const weatherKey = (lat, lon) => `${lat.toFixed(2)},${lon.toFixed(2)}`;

export async function fetchWeather(lat, lon, { signal } = {}) {
  const url = new URL(BASE);
  url.searchParams.set('latitude', String(lat));
  url.searchParams.set('longitude', String(lon));
  url.searchParams.set(
    'current',
    'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m',
  );
  url.searchParams.set(
    'daily',
    'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum',
  );
  url.searchParams.set('timezone', 'auto');
  url.searchParams.set('forecast_days', '7');
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Météo indisponible (${res.status})`);
  return normalize(await res.json());
}

/** Open-Meteo payload → the shape the widget reads (pure, tested). */
export function normalize(json) {
  const c = json.current ?? {};
  const d = json.daily ?? {};
  return {
    current: {
      temp: c.temperature_2m,
      feelsLike: c.apparent_temperature,
      humidity: c.relative_humidity_2m,
      precipitation: c.precipitation,
      wind: c.wind_speed_10m,
      code: c.weather_code,
      time: c.time,
      ...describeWmo(c.weather_code),
    },
    daily: (d.time ?? []).map((date, i) => ({
      date,
      code: d.weather_code?.[i],
      tmax: d.temperature_2m_max?.[i],
      tmin: d.temperature_2m_min?.[i],
      rain: d.precipitation_sum?.[i],
      ...describeWmo(d.weather_code?.[i]),
    })),
    timezone: json.timezone,
    fetchedAt: Date.now(),
  };
}

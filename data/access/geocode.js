/**
 * Address search through OpenStreetMap's Nominatim (free, no key). Fair-use
 * policy: at most one request per second, which a human typing addresses
 * respects. Results are { label, detail, lat, lon }.
 */
const BASE = 'https://nominatim.openstreetmap.org';

function split(displayName) {
  const parts = String(displayName)
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return { label: parts[0] ?? displayName, detail: parts.slice(1, 4).join(', ') };
}

export async function geocode(query, { signal } = {}) {
  const url = new URL(`${BASE}/search`);
  url.searchParams.set('format', 'jsonv2');
  url.searchParams.set('q', query);
  url.searchParams.set('limit', '5');
  url.searchParams.set('accept-language', 'fr');
  const res = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Recherche d’adresse indisponible (${res.status})`);
  const rows = await res.json();
  return rows.map((r) => ({
    ...split(r.display_name),
    lat: Number(r.lat),
    lon: Number(r.lon),
  }));
}

/** Short human label for a point, or null when the service is unreachable. */
export async function reverseGeocode(lat, lon, { signal } = {}) {
  try {
    const url = new URL(`${BASE}/reverse`);
    url.searchParams.set('format', 'jsonv2');
    url.searchParams.set('lat', String(lat));
    url.searchParams.set('lon', String(lon));
    url.searchParams.set('zoom', '16');
    url.searchParams.set('accept-language', 'fr');
    const res = await fetch(url, { signal, headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    const r = await res.json();
    const a = r.address ?? {};
    const town = a.village || a.town || a.city || a.municipality || a.county;
    const road = a.road ? `${a.house_number ? `${a.house_number}, ` : ''}${a.road}` : null;
    const region = a.state ? `, ${a.state}` : '';
    const label = [road, town].filter(Boolean).join(', ');
    return label ? `${label}${region}` : split(r.display_name).label;
  } catch {
    return null;
  }
}

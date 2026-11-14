/** Hash router: #/tableau, #/section/A/rotation, … (works on GitHub Pages without server config). */
const SIMPLE = [
  'connexion',
  'type-de-ferme',
  'localisation',
  'tracer',
  'cultures',
  'priorites',
  'tableau',
  'feux',
  'sources',
  'compte',
];
export const SECTION_TABS = ['champ', 'rotation', 'resultats', 'explorer', 'stress'];

export function parseHash(hash) {
  const parts = String(hash || '')
    .replace(/^#\/?/, '')
    .split('/')
    .filter(Boolean)
    .map(decodeURIComponent);
  if (parts[0] === 'section' && parts[1] && SECTION_TABS.includes(parts[2])) {
    return { name: `section-${parts[2]}`, params: { id: parts[1].toUpperCase(), tab: parts[2] } };
  }
  if (SIMPLE.includes(parts[0])) return { name: parts[0], params: {} };
  return { name: null, params: {} };
}

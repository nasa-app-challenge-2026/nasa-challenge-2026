import { messages } from './messages.js';

let language = 'en';
export const getLanguage = () => language;
export const locale = () => (language === 'fr' ? 'fr-CA' : 'en-CA');
export function setLanguage(value) {
  language = value === 'fr' ? 'fr' : 'en';
}
const normal = (s) => String(s).replace(/\s+/g, ' ').trim();
const escapeRE = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const interpolate = (s, vars) => s.replace(/\{(\w+)\}/g, (whole, key) => vars[key] ?? whole);

/** Source phrases are stable keys for the existing French templates. Named keys support plurals. */
export function t(key, variables = {}) {
  const entry = messages[key];
  let value = entry?.[language] ?? key;
  if (typeof value === 'object')
    value = value[new Intl.PluralRules(locale()).select(variables.count)] ?? value.other;
  return interpolate(value, variables);
}

const patterns = Object.entries(messages)
  .filter(([key, value]) => /\{\d+\}/.test(key) && typeof value.en === 'string' && value.en !== key)
  .sort((a, b) => b[0].replace(/\{\d+\}/g, '').length - a[0].replace(/\{\d+\}/g, '').length)
  .map(([source, value]) => {
    const keys = [...source.matchAll(/\{(\d+)\}/g)].map((m) => m[1]);
    const regex = new RegExp(
      `^${source
        .split(/\{\d+\}/)
        .map(escapeRE)
        .join('(.*?)')}$`,
      's',
    );
    return { source, value: value.en, keys, regex };
  });
const phrases = Object.entries(messages)
  .filter(([key, value]) => !key.includes('{') && typeof value.en === 'string' && value.en !== key)
  .flatMap(([key, value]) => {
    const lower = key.toLowerCase();
    return key.length < 80 && lower !== key && !messages[lower]
      ? [
          [key, value],
          [lower, { en: value.en.toLowerCase() }],
        ]
      : [[key, value]];
  })
  .sort((a, b) => b[0].length - a[0].length);
const phraseMap = new Map(phrases.map(([key, value]) => [key, value.en]));
const phraseRE = new RegExp(
  `(?<![\\p{L}\\p{N}])(?:${phrases.map(([key]) => escapeRE(key)).join('|')})(?![\\p{L}\\p{N}])`,
  'gu',
);
const cache = new Map();

/** Localise legacy display strings, including server messages, without touching domain identifiers. */
export function translateText(value, depth = 0) {
  if (!value || depth > 5) return String(value ?? '');
  if (language === 'fr') return messages[normal(value)]?.fr ?? String(value);
  const source = normal(value);
  if (cache.has(source)) return cache.get(source);
  let result;
  if (messages[source]) result = t(source);
  else {
    for (const pattern of patterns) {
      const match = pattern.regex.exec(source);
      if (!match) continue;
      const vars = Object.fromEntries(
        pattern.keys.map((key, i) => [key, translateText(match[i + 1], depth + 1)]),
      );
      result = interpolate(pattern.value, vars);
      break;
    }
    result ??= source.replace(phraseRE, (phrase) => phraseMap.get(phrase));
  }
  if (cache.size > 3000) cache.clear();
  cache.set(source, result);
  return result;
}

export const formatNumber = (n, options = {}) => new Intl.NumberFormat(locale(), options).format(n);
export const formatDate = (date, options = {}) =>
  new Intl.DateTimeFormat(locale(), { timeZone: 'UTC', ...options }).format(new Date(date));
export const pluralText = (n, one, other) =>
  `${formatNumber(n)} ${translateText(new Intl.PluralRules(locale()).select(n) === 'one' ? one : other)}`;

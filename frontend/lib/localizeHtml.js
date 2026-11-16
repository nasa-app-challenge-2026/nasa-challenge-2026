import { translateText } from '../../data/i18n/index.js';

const entities = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'" };
const decode = (s) => s.replace(/&(?:amp|lt|gt|quot|#39);/g, (e) => entities[e]);
const encode = (s) =>
  s.replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const translated = (text) => {
  if (!text.trim()) return text;
  const lead = text.match(/^\s*/)[0];
  const tail = text.match(/\s*$/)[0];
  const source = decode(text);
  const result = translateText(source);
  if (result === source.replace(/\s+/g, ' ').trim()) return text;
  return lead + encode(result) + tail;
};

/** The legacy html tag localises only text and human-readable attributes, never routes, IDs or styles.
 * User-authored content is protected with verbatim(). No DOM walk or mutation observer is needed.
 */
export function localizeHtml(markup) {
  // Nested safe templates may be attribute fragments rather than element content.
  if (!markup.includes('<') && /^\s*[\w-]+\s*=/.test(markup)) return markup;
  return markup
    .split(/(<!--i18n:off-->[\s\S]*?<!--i18n:on-->)/g)
    .map((part) => {
      if (part.startsWith('<!--i18n:off-->')) return part;
      return part
        .split(/(<[^>]*>)/g)
        .map((token) =>
          token.startsWith('<')
            ? token.replace(
                /\b(aria-label|title|placeholder|alt|data-title)="([^"]*)"/g,
                (_all, attribute, value) => `${attribute}="${translated(value)}"`,
              )
            : translated(token),
        )
        .join('');
    })
    .join('');
}

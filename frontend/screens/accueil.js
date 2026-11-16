import { html } from '../lib/html.js';
import { languageButton } from '../ui/layout.js';
import { getLanguage } from '../../data/i18n/index.js';
import { logo } from '../ui/widgets.js';

const COPY = {
  en: {
    tag: 'NASA SPACE APPS CHALLENGE · 2026',
    title: 'Tomorrow’s climate.',
    emphasis: 'Today’s seeds.',
    intro:
      'A changing climate calls for new crop rotations. FarmShift connects satellite data with the knowledge of the field to help farmers explore what comes next.',
    app: 'Enter FarmShift',
    paper: 'Read the research',
    appHint: 'Explore the farm',
    paperHint: 'Follow the science',
    pdf: 'Research paper · PDF ↗',
    scroll: 'From space to soil',
    problem: 'The seasons are changing.\nOur fields can adapt.',
    problemText:
      'What should we grow when rainfall, heat and frost no longer follow familiar patterns? Start with your field, look for places that already experience its future climate, then compare possible crop sequences.',
    dataLabel: '01 / OBSERVE',
    dataTitle: 'A wider view.\nA closer understanding.',
    dataIntro:
      'Different sources tell different parts of the story. Together, they put each field in context.',
    sources: [
      [
        'NASA POWER',
        'Weather over time',
        'Temperature, rainfall and atmospheric conditions help describe the farm’s climate.',
      ],
      [
        'NEX-GDDP-CMIP6',
        'Possible futures',
        'Climate projections extend the view beyond the near-term weather trend.',
      ],
      [
        'Soil & crop maps',
        'The reality of the field',
        'SoilGrids and crop maps from AAFC and USDA connect climate with soil and farming practices.',
      ],
    ],
    methodLabel: '02 / CONNECT',
    methodTitle: 'A rotation is a story.\nEvery crop shapes the next.',
    steps: [
      [
        'Know the field',
        'Locate the farm and describe its sections, crops, seed reserve and priorities.',
      ],
      [
        'Find climate twins',
        'Look for places whose observed climate resembles the farm’s projected climate.',
      ],
      [
        'Build crop sequences',
        'Consider crop suitability, sowing and harvest dates, frost and return periods.',
      ],
      [
        'Compare the possibilities',
        'Explore recommended rotations alongside the current one, through yield, water, soil protection and pests.',
      ],
    ],
    note: 'A decision-support prototype developed for a hackathon. Results depend on available data and model assumptions; agronomic validation remains essential.',
    evidenceLabel: '03 / FROM DATA TO DECISIONS',
    evidenceTitle: 'Open data.\nRooted in real fields.',
    evidenceIntro:
      'Six complementary families of sources connect climate, satellite observations and agronomy. Their strength is in how we bring them together for each field.',
    evidence: [
      [
        'Read the seasons',
        'Forty years of NASA POWER weather and three CMIP6 climate scenarios help locate the present-day regions that resemble the farm’s future.',
        'NASA POWER · NEX-GDDP-CMIP6',
      ],
      [
        'Learn from other fields',
        'Canadian and U.S. crop maps, at 30-metre resolution, reveal the crop sequences actually grown in climate-twin regions.',
        'AAFC Annual Crop Inventory · USDA CDL',
      ],
      [
        'Observe plant growth',
        'MODIS vegetation indices help explore how a preceding crop affects the next. This is an experimental indicator, not a direct measurement of yield.',
        'MODIS · EVI / NDVI',
      ],
      [
        'Understand the soil',
        'Soil texture, organic carbon and pH help select comparable fields and estimate how water moves through and is stored in the soil.',
        'SoilGrids 2.0 · SSURGO',
      ],
      [
        'Read the landscape',
        'Elevation models reveal slopes, helping assess erosion risk and the value of keeping the ground covered.',
        'Copernicus DEM · SRTM',
      ],
      [
        'Ground the choices in agronomy',
        'Published rotation rules guide crop return periods and pressure from 43 soilborne organisms. Water and erosion models complete the comparison.',
        'Fruchtfolge · SARE · FAO-56 · RUSLE',
      ],
    ],
    evidenceResult:
      'From space to the next sowing: climate twins identify relevant farming practices, field conditions constrain the options, and your priorities guide the ranking of rotations.',
    evidenceLink: 'Where the data comes from · Research paper, p. 4',
    endLabel: 'YOUR NEXT STEP',
    endTitle: 'Explore the field.\nOr dig into the research.',
    endText: 'Two ways into the same question: how can our farms adapt?',
    footer: 'Built by HUMANITY.EXE TEAM · NASA Space Apps Challenge 2026',
    home: 'Project home',
  },
  fr: {
    tag: 'NASA SPACE APPS CHALLENGE · 2026',
    title: 'Le climat de demain.',
    emphasis: 'Les semences d’aujourd’hui.',
    intro:
      'Un climat qui change appelle de nouvelles rotations. FarmShift relie les données satellites à la réalité du terrain pour aider les fermiers à explorer la suite.',
    app: 'Accéder à FarmShift',
    paper: 'Lire la recherche',
    appHint: 'Explorer la ferme',
    paperHint: 'Comprendre la science',
    pdf: 'Papier de recherche · PDF ↗',
    scroll: 'De l’espace à la terre',
    problem: 'Les saisons changent.\nNos champs peuvent s’adapter.',
    problemText:
      'Que cultiver quand la pluie, la chaleur et le gel ne suivent plus les mêmes habitudes ? Partir de sa parcelle, trouver des endroits qui connaissent déjà son climat futur, puis comparer les suites de cultures possibles.',
    dataLabel: '01 / OBSERVER',
    dataTitle: 'Prendre de la hauteur.\nComprendre le terrain.',
    dataIntro:
      'Chaque source éclaire une partie du problème. Ensemble, elles donnent du contexte à chaque parcelle.',
    sources: [
      [
        'NASA POWER',
        'La météo dans le temps',
        'Température, pluie et conditions atmosphériques décrivent le climat de la ferme.',
      ],
      [
        'NEX-GDDP-CMIP6',
        'Les futurs possibles',
        'Les projections climatiques prolongent le regard au-delà de la tendance météo à court terme.',
      ],
      [
        'Cartes des sols et cultures',
        'La réalité des champs',
        'SoilGrids et les cartes de cultures d’AAC et de l’USDA relient climat, sol et pratiques agricoles.',
      ],
    ],
    methodLabel: '02 / RELIER',
    methodTitle: 'Une rotation est une histoire.\nChaque culture prépare la suivante.',
    steps: [
      [
        'Connaître la parcelle',
        'Situer la ferme et décrire ses sections, ses cultures, ses semences et ses priorités.',
      ],
      [
        'Trouver ses jumeaux climatiques',
        'Chercher des endroits dont le climat observé ressemble au climat projeté pour la ferme.',
      ],
      [
        'Construire les suites de cultures',
        'Tenir compte des cultures adaptées, du calendrier, du gel et des délais de retour.',
      ],
      [
        'Comparer les possibilités',
        'Explorer les rotations proposées face à la rotation actuelle : rendement, eau, protection du sol et ravageurs.',
      ],
    ],
    note: 'Un prototype d’aide à la décision développé pour un hackathon. Les résultats dépendent des données disponibles et des hypothèses des modèles ; une validation agronomique reste essentielle.',
    evidenceLabel: '03 / DES DONNÉES AUX CHOIX',
    evidenceTitle: 'Des données ouvertes.\nDes racines dans le terrain.',
    evidenceIntro:
      'Six familles de sources complémentaires relient climat, observations satellites et agronomie. Notre force : les croiser à l’échelle de chaque parcelle.',
    evidence: [
      [
        'Lire les saisons',
        'Quarante ans de météo NASA POWER et trois scénarios climatiques CMIP6 aident à repérer les régions dont le climat actuel ressemble au futur de la ferme.',
        'NASA POWER · NEX-GDDP-CMIP6',
      ],
      [
        'Apprendre des autres champs',
        'Les cartes canadiennes et américaines, à 30 mètres de résolution, révèlent les successions de cultures réellement pratiquées dans les régions jumelles.',
        'AAC — Inventaire annuel des cultures · USDA CDL',
      ],
      [
        'Observer la croissance',
        'Les indices de végétation MODIS aident à explorer l’effet d’une culture sur la suivante. C’est un indicateur expérimental, pas une mesure directe du rendement.',
        'MODIS · EVI / NDVI',
      ],
      [
        'Comprendre le sol',
        'Texture, carbone organique et pH permettent de sélectionner des parcelles comparables et d’estimer comment l’eau circule et se conserve dans le sol.',
        'SoilGrids 2.0 · SSURGO',
      ],
      [
        'Lire le relief',
        'Les modèles d’altitude révèlent les pentes pour évaluer le risque d’érosion et l’intérêt de maintenir le sol couvert.',
        'Copernicus DEM · SRTM',
      ],
      [
        'Ancrer les choix dans l’agronomie',
        'Des références agronomiques encadrent les délais de retour des cultures et la pression de 43 organismes du sol. Les modèles d’eau et d’érosion complètent la comparaison.',
        'Fruchtfolge · SARE · FAO-56 · RUSLE',
      ],
    ],
    evidenceResult:
      'De l’espace aux prochaines semences : les jumeaux climatiques révèlent des pratiques pertinentes, les conditions du terrain encadrent les possibilités et vos priorités orientent le classement des rotations.',
    evidenceLink: 'D’où viennent les données · Papier de recherche, p. 4',
    endLabel: 'À VOUS DE CHOISIR',
    endTitle: 'Explorez la ferme.\nOu les racines de la recherche.',
    endText: 'Deux portes d’entrée pour une même question : comment adapter nos fermes ?',
    footer: 'Créé par HUMANITY.EXE TEAM · NASA Space Apps Challenge 2026',
    home: 'Accueil du projet',
  },
};

const sprout = () =>
  html`<svg viewBox="0 0 50 50" aria-hidden="true">
    <path
      d="M25 45V24C6 28 3 12 6 7c14 0 22 6 19 17C26 9 37 6 46 8c0 13-8 21-21 16"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
    />
  </svg>`;
const vine = (flip = false) =>
  html`<svg
    class="hub-vine ${flip ? 'hub-vine--flip' : ''}"
    viewBox="0 0 160 110"
    aria-hidden="true"
  >
    <path
      d="M20 5C110 0 10 70 125 84M106 67l23 18-27 14"
      fill="none"
      stroke="currentColor"
      stroke-width="2.5"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M51 21Q40-2 65 7Q77 24 51 21M52 54Q18 35 29 63Q43 74 52 54M85 78Q91 46 106 58Q110 77 85 78"
      fill="currentColor"
    />
  </svg>`;
function doors(s, c, arrows = false) {
  const href = !s.user ? '#/connexion' : s.onboarded ? '#/tableau' : '#/type-de-ferme';
  return html`<div class="hub-doors">
    <div>
      ${arrows ? vine() : ''}<span class="hub-hand">${c.appHint}</span
      ><a class="hub-door hub-door--green" href="${href}"
        >${sprout()}<span>${c.app}</span><span aria-hidden="true">↗</span></a
      >
    </div>
    <div>
      ${arrows ? vine(true) : ''}<span class="hub-hand">${c.paperHint}</span
      ><a class="hub-door hub-door--paper" href="research-paper.pdf" target="_blank" rel="noopener"
        >${sprout()}<span>${c.paper}</span><span aria-hidden="true">↗</span></a
      ><small>${c.pdf}</small>
    </div>
  </div>`;
}
function landscape() {
  return html`<svg
    class="hub-landscape"
    viewBox="0 0 1400 320"
    aria-hidden="true"
    preserveAspectRatio="xMidYMax slice"
  >
    <circle cx="1100" cy="85" r="55" fill="#e8c96e" />
    <path d="M0 160Q250 20 510 155T1000 145T1400 100V320H0Z" fill="#cbd8b8" />
    <path d="M0 240Q340 60 700 220Q1080 80 1400 210V320H0Z" fill="#789564" />
    <path d="M0 280Q450 100 850 270Q1100 180 1400 260V320H0Z" fill="#31573b" />
    <g fill="none" stroke="#b4c397" stroke-width="2" opacity=".65">
      ${[0, 1, 2, 3, 4, 5, 6].map((i) => html`<path d="M${i * 120 - 100} 320Q${i * 65 + 250} 170 650 210" />`)}
      <path d="M820 320Q1100 210 1400 295M970 320Q1200 250 1400 310" />
    </g>
    <g transform="translate(260 108)">
      <path d="M0 35L50 0l50 35v62H0Z" fill="#f3e9ce" />
      <path d="M-8 36L50-9l58 45" fill="none" stroke="#664c35" stroke-width="8" />
      <path d="M37 97V50h28v47" fill="#31573b" />
      <path d="M112 97V20q18-26 36 0v77" fill="#a6b894" />
    </g>
  </svg>`;
}
let removeScrollListener;
export default {
  title: 'FarmShift',
  mount() {
    removeScrollListener?.();
    const bar = document.querySelector('.hub-access');
    const heroDoors = document.querySelector('.hub-hero .hub-doors');
    if (!bar || !heroDoors) return;
    const update = () => {
      const visible = heroDoors.getBoundingClientRect().bottom < 0;
      bar.classList.toggle('is-visible', visible);
      bar.inert = !visible;
      bar.setAttribute('aria-hidden', String(!visible));
    };
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    removeScrollListener = () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
    update();
  },
  unmount() {
    removeScrollListener?.();
    removeScrollListener = undefined;
  },
  render(state) {
    const c = COPY[getLanguage()];
    return html`<div class="hub">
      <nav class="hub-access" aria-label="${c.home}" aria-hidden="true" inert>
        <a class="hub-access__brand" href="#/accueil">${logo()}</a>
        ${doors(state, c)}
      </nav>
      <header class="hub-nav">
        <a href="#/accueil" aria-label="${c.home}">${logo()}</a
        ><span class="hub-nav__tag">HUMANITY.EXE TEAM / 2026</span>${languageButton()}
      </header>
      <main id="main">
        <section class="hub-hero">
          <p class="hub-eyebrow">${c.tag}</p>
          <h1>${c.title}<br /><em>${c.emphasis}</em></h1>
          <p class="hub-intro">${c.intro}</p>
          ${doors(state, c, true)}
          <p class="hub-scroll">${c.scroll}<span aria-hidden="true">↓</span></p>
          ${landscape()}
        </section>
        <section class="hub-story hub-section">
          <div class="hub-seal">
            ${sprout()}<span>SPACE<br />TO SOIL</span>
          </div>
          <h2>${c.problem}</h2>
          <p>${c.problemText}</p>
        </section>
        <section class="hub-data hub-section">
          <div class="hub-section-head">
            <p class="hub-eyebrow">${c.dataLabel}</p>
            <h2>${c.dataTitle}</h2>
            <p>${c.dataIntro}</p>
          </div>
          <div class="hub-sources">
            ${c.sources.map(
              ([name, title, body], i) =>
                html`<article>
                  <span class="hub-source-number">0${i + 1} /</span>
                  <h3>${title}</h3>
                  <p>${body}</p>
                  <span class="hub-source-name">${name}</span>
                </article>`,
            )}
          </div>
        </section>
        <section class="hub-method hub-section">
          <div class="hub-section-head">
            <p class="hub-eyebrow">${c.methodLabel}</p>
            <h2>${c.methodTitle}</h2>
            ${sprout()}
          </div>
          <ol>
            ${c.steps.map(
              ([title, body], i) =>
                html`<li>
                  <span class="hub-step">${i + 1}</span>
                  <div>
                    <h3>${title}</h3>
                    <p>${body}</p>
                  </div>
                </li>`,
            )}
          </ol>
        </section>
        <section class="hub-evidence hub-section" aria-labelledby="hub-evidence-title">
          <div class="hub-section-head">
            <p class="hub-eyebrow">${c.evidenceLabel}</p>
            <h2 id="hub-evidence-title">${c.evidenceTitle}</h2>
            <p>${c.evidenceIntro}</p>
          </div>
          <div class="hub-evidence__branches">
            ${c.evidence.map(
              ([title, body, source]) =>
                html`<article>
                  <div class="hub-evidence__leaf">${sprout()}</div>
                  <h3>${title}</h3>
                  <p>${body}</p>
                  <span class="hub-source-name">${source}</span>
                </article>`,
            )}
          </div>
          <div class="hub-evidence__result">
            <p>${c.evidenceResult}</p>
            <a href="research-paper.pdf#page=4" target="_blank" rel="noopener"
              >${c.evidenceLink}<span aria-hidden="true"> ↗</span></a
            >
          </div>
        </section>
        <section class="hub-end hub-section">
          <p class="hub-eyebrow">${c.endLabel}</p>
          <h2>${c.endTitle}</h2>
          <p>${c.endText}</p>
          ${doors(state, c)}
          <p class="hub-note">${c.note}</p>
        </section>
      </main>
      <footer class="hub-footer">${logo()}<span>${c.footer}</span></footer>
    </div>`;
  },
};

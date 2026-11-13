/**
 * Screen registry. A screen is { title, render(state, params, app), actions?, onEnter?, rota? }.
 * Owners (see docs/TEAM.md): Ali = tableau, rotation · Loïc = connexion, type-de-ferme,
 * localisation, tracer, priorites, compte, RotaAI · Justin = champ, resultats, explorer,
 * stress, sources.
 */
import connexion from './connexion.js';
import typeFerme from './typeFerme.js';
import localisation from './localisation.js';
import tracer from './tracer.js';
import priorites from './priorites.js';
import tableau from './tableau.js';
import champ from './champ.js';
import rotation from './rotation.js';
import resultats from './resultats.js';
import explorer from './explorer.js';
import stress from './stress.js';
import sources from './sources.js';
import compte from './compte.js';

export const SCREENS = {
  connexion,
  'type-de-ferme': typeFerme,
  localisation,
  tracer,
  priorites,
  tableau,
  'section-champ': champ,
  'section-rotation': rotation,
  'section-resultats': resultats,
  'section-explorer': explorer,
  'section-stress': stress,
  sources,
  compte,
};

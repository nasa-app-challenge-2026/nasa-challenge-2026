/**
 * Screen registry. A screen is { title, render(state, params, app), actions?, onEnter?, rota? }.
 * Owners (see docs/TEAM.md): Ali = tableau, parcelle · Loïc = connexion, type-de-ferme,
 * localisation, tracer, cultures, temps, priorites, compte, Rota · Justin = champ, plan,
 * jumeaux, sources.
 */
import connexion from './connexion.js';
import accueil from './accueil.js';
import typeFerme from './typeFerme.js';
import localisation from './localisation.js';
import tracer from './tracer.js';
import cultures from './cultures.js';
import priorites from './priorites.js';
import tableau from './tableau.js';
import champ from './champ.js';
import parcelle from './parcelle.js';
import plan from './plan.js';
import jumeaux from './jumeaux.js';
import temps from './temps.js';
import sources from './sources.js';
import compte from './compte.js';

export const SCREENS = {
  accueil,
  connexion,
  'type-de-ferme': typeFerme,
  localisation,
  tracer,
  cultures,
  temps,
  priorites,
  tableau,
  'section-parcelle': parcelle,
  'section-champ': champ,
  'section-plan': plan,
  'section-jumeaux': jumeaux,
  sources,
  compte,
};

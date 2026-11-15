/**
 * Step 1, block A: what the farmer tells about each section (crop in place and its
 * harvest month, previous years, current rotation, known soil diseases, irrigation,
 * soil test). Pure helpers that edit a section of the FarmInput (a store draft).
 */
import { SHEETS } from '../../data/reference/crops.js';
import { MIN_HISTORY_YEARS } from '../../data/reference/planning.js';

/** A new section: nothing known yet. */
export const blankSection = (id) => ({
  id,
  areaHa: 1,
  polygon: [],
  currentCrop: null,
  currentHarvest: null,
  history: [],
  currentRotation: [],
  rotationPosition: 0,
  diseases: [],
  irrigated: false,
  soilTest: null,
});

const yearOfMonth = (yearMonth) => (yearMonth ? Number(yearMonth.slice(0, 4)) : null);

/** First year occupied by the crop in place (a perennial started earlier). */
export function inPlaceFirstYear(section) {
  const freeYear = yearOfMonth(section.currentHarvest);
  if (freeYear === null) return null;
  return freeYear - Math.max(SHEETS[section.currentCrop]?.productionYears ?? 0, 1) + 1;
}

/**
 * The years of history to ask, most recent first: the years before the crop in
 * place (or before `currentYear` when the section is free).
 */
export function historyYearsToAsk(section, currentYear, count = MIN_HISTORY_YEARS) {
  const before = inPlaceFirstYear(section) ?? currentYear + 1;
  return Array.from({ length: count }, (_, i) => before - 1 - i);
}

export const historyCropOf = (section, year) =>
  section.history.find((h) => h.year === year)?.crop ?? null;

/** Set (or clear with null) the crop of one past year. */
export function setHistoryCrop(section, year, crop) {
  section.history = section.history.filter((h) => h.year !== year);
  if (crop) section.history.push({ year, crop });
  section.history.sort((a, b) => a.year - b.year);
}

/** The crop in place; a crop not in the current rotation is added to it. */
export function setCurrentCrop(section, crop, defaultHarvest) {
  section.currentCrop = crop;
  if (!crop) {
    section.currentHarvest = null;
    return;
  }
  section.currentHarvest = section.currentHarvest ?? defaultHarvest;
  const at = section.currentRotation.indexOf(crop);
  if (SHEETS[crop] && at < 0 && section.currentRotation.length === 0) {
    section.currentRotation = [crop];
    section.rotationPosition = 0;
  } else if (at >= 0) section.rotationPosition = at;
}

export function addToRotation(section, sheetId) {
  section.currentRotation = [...section.currentRotation, sheetId];
}

export function removeFromRotation(section, index) {
  section.currentRotation = section.currentRotation.filter((_, i) => i !== index);
  if (section.rotationPosition >= section.currentRotation.length) section.rotationPosition = 0;
}

export function moveInRotation(section, index, delta) {
  const j = index + delta;
  const r = [...section.currentRotation];
  if (j < 0 || j >= r.length) return;
  [r[index], r[j]] = [r[j], r[index]];
  section.currentRotation = r;
  if (section.rotationPosition === index) section.rotationPosition = j;
  else if (section.rotationPosition === j) section.rotationPosition = index;
}

export function toggleDisease(section, diseaseId) {
  section.diseases = section.diseases.includes(diseaseId)
    ? section.diseases.filter((d) => d !== diseaseId)
    : [...section.diseases, diseaseId];
}

/** What is missing or inconsistent in a section's inputs (empty = fine). */
export function sectionInputProblems(section) {
  const problems = [];
  if (section.currentCrop && !section.currentHarvest)
    problems.push('Indiquez le mois de récolte de la culture en place.');
  if (section.currentRotation.length && section.currentCrop && SHEETS[section.currentCrop]) {
    if (section.currentRotation[section.rotationPosition] !== section.currentCrop)
      problems.push(
        'La position actuelle dans la rotation ne correspond pas à la culture en place.',
      );
  }
  return problems;
}

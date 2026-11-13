/**
 * Soil-health roles per year, from the crop and cover catalogues.
 * This is a count of roles (structural), not a score: the soil *score* comes
 * from the engine.
 */
import { CROPS, COVERS, SOIL_ROLES } from '../data/crops.js';
import { toSlots } from './rotation.js';

/** Roles present in one year (crop roles + cover roles). */
export function rolesOfYear(crop, cover) {
  const roles = new Set(CROPS[crop]?.roles ?? []);
  if (cover && CROPS[crop]?.years === 1) COVERS[cover]?.roles.forEach((r) => roles.add(r));
  return roles;
}

/** For each soil role: one boolean per year of the cycle. */
export function soilByCycleYear(rotation) {
  const slots = toSlots(rotation);
  return Object.fromEntries(
    SOIL_ROLES.map((role) => [role, slots.map((s) => rolesOfYear(s.crop, s.cover).has(role))]),
  );
}

/** For each soil role: one boolean per year of a calendar (see buildCalendar). */
export function soilByCalendar(calendar) {
  return Object.fromEntries(
    SOIL_ROLES.map((role) => [role, calendar.map((y) => rolesOfYear(y.crop, y.cover).has(role))]),
  );
}

export const countTrue = (arr) => arr.filter(Boolean).length;

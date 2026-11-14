/**
 * FICTITIOUS satellite measures of a field (step 8) and its SoilGrids soil (step 5).
 * Real values: SRTM / NASADEM slope, GPM IMERG heavy rain days, MODIS / HLS bare
 * soil days, ECOSTRESS ESI, SMAP L4 root-zone drought, GRACE-FO, SoilGrids 2.0.
 * They start from the demo field of field_shift.py and vary a little from one
 * section to the next, so that two sections do not look identical.
 */
const BASE_MEASURES = {
  slopePct: 6,
  heavyRainDays: 6,
  bareSoilDays: 120,
  summerStressIndex: 0.6,
  rootZoneDrought: 0.4,
  groundwaterTrendCmPerYear: -1,
};
/** How much each measure varies between sections (± this amount). */
const SECTION_VARIATION = {
  slopePct: 3,
  heavyRainDays: 2,
  bareSoilDays: 30,
  summerStressIndex: 0.1,
  rootZoneDrought: 0.15,
  groundwaterTrendCmPerYear: 0.5,
};
const BASE_SOIL = { clayPct: 30, sandPct: 25, organicCarbon: 25, ph: 6.5 };
const SOIL_VARIATION = { clayPct: 8, sandPct: 12, organicCarbon: 6, ph: 0.4 };
/** Decimals shown for each value (days are whole numbers). */
const DECIMALS = {
  slopePct: 1,
  heavyRainDays: 0,
  bareSoilDays: 0,
  summerStressIndex: 2,
  rootZoneDrought: 2,
  groundwaterTrendCmPerYear: 1,
  clayPct: 0,
  sandPct: 0,
  organicCarbon: 1,
  ph: 1,
};
const roundTo = (value, decimals) => Math.round(value * 10 ** decimals) / 10 ** decimals;

/** A number from −1 to 1 that depends only on the section id (stable between visits). */
function sectionShift(sectionId, salt) {
  const text = `${sectionId}:${salt}`;
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0;
  return ((h % 2001) - 1000) / 1000;
}

const varied = (base, variation, sectionId) =>
  Object.fromEntries(
    Object.entries(base).map(([key, value]) => [
      key,
      roundTo(value + variation[key] * sectionShift(sectionId, key), DECIMALS[key]),
    ]),
  );

export const demoFieldMeasures = (sectionId) => varied(BASE_MEASURES, SECTION_VARIATION, sectionId);
export const demoSoil = (sectionId) => varied(BASE_SOIL, SOIL_VARIATION, sectionId);

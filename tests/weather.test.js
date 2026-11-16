import { beforeEach, describe, expect, it } from 'vitest';
import { setLanguage } from '../data/i18n/index.js';
beforeEach(() => setLanguage('fr'));
import { describeWmo, normalize, weatherKey } from '../data/access/weather.js';
import { dayLabel } from '../frontend/ui/weatherWidget.js';

describe('weather', () => {
  it('maps WMO codes to French labels', () => {
    expect(describeWmo(0)).toEqual({ label: 'Ciel dégagé', icon: 'sun' });
    expect(describeWmo(63).icon).toBe('rain');
    expect(describeWmo(95).label).toBe('Orage');
    expect(describeWmo(999).icon).toBe('cloud');
  });

  it('normalises an Open-Meteo payload', () => {
    const data = normalize({
      timezone: 'America/Toronto',
      current: {
        time: '2026-11-12T10:00',
        temperature_2m: 4.2,
        apparent_temperature: 1,
        relative_humidity_2m: 80,
        precipitation: 0.3,
        weather_code: 61,
        wind_speed_10m: 18,
      },
      daily: {
        time: ['2026-11-12', '2026-11-13'],
        weather_code: [61, 3],
        temperature_2m_max: [6, 8],
        temperature_2m_min: [1, 2],
        precipitation_sum: [4.2, 0],
      },
    });
    expect(data.current.temp).toBe(4.2);
    expect(data.current.label).toBe('Pluie');
    expect(data.daily).toHaveLength(2);
    expect(data.daily[1]).toMatchObject({ date: '2026-11-13', tmax: 8, tmin: 2, icon: 'cloud' });
    expect(typeof data.fetchedAt).toBe('number');
  });

  it('labels the days in French, today first', () => {
    expect(dayLabel('2026-11-12', 0)).toBe('Auj.');
    expect(dayLabel('2026-11-13', 1)).toBe('ven.');
    expect(weatherKey(45.6287, -72.94815)).toBe('45.63,-72.95');
  });
});

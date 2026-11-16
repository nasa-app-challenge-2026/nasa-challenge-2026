/* global localStorage, document, location, innerWidth, getComputedStyle */
// Optional browser verification; Playwright is installed in .qa, never in application dependencies.
import { chromium } from '../.qa/node_modules/playwright-core/index.mjs';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DEMO_FARM } from '../data/reference/demoFarm.js';
const plan = JSON.parse(readFileSync('backend/contract/examples/ferme-demo.plan.json', 'utf8'));
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const results = [];
try {
  for (const width of [1440, 390])
    for (const language of ['en', 'fr']) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      await page.route('**/plan', (route) =>
        route.fulfill({ json: plan, headers: { 'Access-Control-Allow-Origin': '*' } }),
      );
      await page.route('**/api.open-meteo.com/**', (route) => route.abort());
      await page.addInitScript(
        ({ farm, plan, language }) => {
          if (localStorage.getItem('qa-seeded')) return;
          localStorage.setItem('qa-seeded', 'true');
          localStorage.setItem(
            'field-shift:v2',
            JSON.stringify({ user: { name: 'Test' }, onboarded: true, farm, prefs: { language } }),
          );
          localStorage.setItem(
            'field-shift:plan:v3',
            JSON.stringify({ key: JSON.stringify(farm), data: plan }),
          );
        },
        { farm: DEMO_FARM, plan, language },
      );
      await page.goto('http://127.0.0.1:5173/#/tableau');
      await page.waitForSelector('[data-section-card]');
      await page.waitForTimeout(700);
      assert.equal(await page.locator('html').getAttribute('lang'), language);
      assert.equal(await page.locator('.farm3d a[href$="/parcelle"]').count(), 0);
      assert.equal(await page.locator('[data-action="open-section"]').count(), 4);
      assert(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        'dashboard overflow',
      );
      // A click in card content navigates; the full-card button is the pointer target.
      const card = page.locator('[data-section-card="A"]');
      await card.hover();
      await card.locator('.widget__hit').click({ position: { x: 25, y: 75 } });
      await page.waitForURL('**/#/section/A/plan');
      await page.waitForSelector('.rot-card');
      assert.equal(await page.locator('.rot-cards > .rot-card').count(), 4);
      assert.equal(await page.locator('.rotation-detail:visible').count(), 0);
      for (let i = 0; i < 4; i++) {
        const trigger = page.locator('[data-action="open-rotation"]').nth(i);
        const id = await trigger.getAttribute('id');
        if (i % 2) {
          await trigger.focus();
          await page.keyboard.press(i === 1 ? 'Enter' : 'Space');
        } else await trigger.click();
        await page.waitForSelector('dialog[open]');
        await page.waitForTimeout(500);
        assert.equal(await page.locator('dialog').getAttribute('role'), 'dialog');
        assert.equal(await page.evaluate(() => document.body.style.overflow), 'hidden');
        assert(
          await page.evaluate(() =>
            document.querySelector('dialog').contains(document.activeElement),
          ),
        );
        await page.locator('.rotation-dialog__close').focus();
        await page.keyboard.press('Shift+Tab');
        assert(
          await page.evaluate(() =>
            document.querySelector('dialog').contains(document.activeElement),
          ),
          'focus trap reverse',
        );
        await page.keyboard.press('Tab');
        assert.equal(
          await page.evaluate(() => document.activeElement.className),
          'rotation-dialog__close',
        );
        assert.equal(await page.locator('dialog .score').count(), 4);
        if (i === 0) {
          await page.locator('dialog [data-topic="calendrier"]').click();
          assert((await page.locator('.rotation-dialog__answer').innerText()).length > 100);
          await page.screenshot({ path: `.qa/rotation-${language}-${width}.png` });
        }
        if (i === 0) await page.locator('.rotation-dialog__close').click();
        else if (i === 2) await page.mouse.click(2, 2);
        else await page.keyboard.press('Escape');
        await page.waitForSelector('dialog', { state: 'detached' });
        assert.equal(await page.evaluate(() => document.body.style.overflow), '');
        assert.equal(await page.evaluate(() => document.activeElement.id), id);
      }
      assert(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        'plan overflow',
      );
      // Cycle and section persist through language switching.
      await page.locator('[data-cycle="2"]').click();
      await page.locator('#language-toggle').click();
      await page.waitForFunction((lang) => document.documentElement.lang !== lang, language);
      assert.equal(await page.locator('[data-cycle="2"]').getAttribute('aria-selected'), 'true');
      assert(page.url().endsWith('/section/A/plan'));
      await page.reload();
      await page.waitForSelector('.rot-card');
      assert.equal(
        await page.locator('html').getAttribute('lang'),
        language === 'en' ? 'fr' : 'en',
      );
      // Programmatic cycle change while modal is open (background controls are inert for users).
      await page.locator('[data-action="open-rotation"]').first().click();
      await page.evaluate(() => document.querySelector('[data-cycle="2"]').click());
      await page.waitForSelector('dialog', { state: 'detached' });
      assert.equal(await page.evaluate(() => document.body.style.overflow), '');
      await page.evaluate(() => (location.hash = '#/tableau'));
      await page.waitForSelector('[data-section-card]');
      const handle = page.locator('#drag-sec-A');
      await handle.focus();
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(300);
      assert.equal(
        await page.locator('[data-sort-id]').first().getAttribute('data-sort-id'),
        'sec:B',
      );
      assert(page.url().endsWith('/tableau'));
      // Actual pointer drag must reorder without opening a section.
      await handle.scrollIntoViewIfNeeded();
      const from = await handle.boundingBox();
      const to = await page.locator('[data-sort-id="sec:B"]').boundingBox();
      await page.mouse.move(from.x + 10, from.y + 10);
      await page.mouse.down();
      await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 12 });
      await page.mouse.up();
      await page.waitForTimeout(500);
      assert(page.url().endsWith('/tableau'));
      await page.locator('[data-action="open-section"]').first().focus();
      await page.keyboard.press('Space');
      await page.waitForURL('**/plan');
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.locator('[data-action="open-rotation"]').first().click();
      assert(
        await page.evaluate(
          () =>
            document.querySelector('.rotation-dialog__front') &&
            getComputedStyle(document.querySelector('.rotation-dialog__front')).display === 'none',
        ),
      );
      await page.keyboard.press('Escape');
      await page.waitForSelector('dialog', { state: 'detached' });
      assert.deepEqual(errors, []);
      results.push(
        `${language} ${width}px: cards, dialog, focus, mouse/keyboard, language, persistence, cycles, drag, reduced motion OK`,
      );
      await page.close();
    }
  console.log(results.join('\n'));
} finally {
  await browser.close();
}

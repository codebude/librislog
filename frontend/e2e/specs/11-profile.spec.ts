import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Profile', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('11.1 view profile', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/profile|e2e|tester/i);
	});

	test('11.2 change language to German', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1500);

		await page.locator('select[name="language"]').selectOption('de');

		await page.locator('#section-language button[class*="btn-primary"]').click();
		await page.waitForTimeout(1000);

		const alert = page.locator('#section-language .alert');
		await expect(alert).toBeVisible({ timeout: 5000 });
	});

	test('11.3 change theme to dracula', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1500);

		await page.locator('select[name="custom-theme"]').selectOption('dracula');

		await page.locator('#section-theme button[class*="btn-primary"]').click();
		await page.waitForTimeout(1000);

		const saved = page.locator('#section-theme').getByText(/saved|gespeichert/i);
		await expect(saved).toBeVisible({ timeout: 5000 });

		const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
		expect(theme).toBe('dracula');
	});

	test('11.3b change theme to catppuccin flavors', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1500);

		const catppuccinOptions = await page
			.locator('select[name="custom-theme"] optgroup[label="Catppuccin"] option')
			.evaluateAll((options) =>
				options.map((option) => ({
					value: (option as HTMLOptionElement).value,
					label: option.textContent?.trim()
				}))
			);
		expect(catppuccinOptions).toEqual([
			{ value: 'latte', label: 'Catppuccin Latte' },
			{ value: 'frappe', label: 'Catppuccin Frappé' },
			{ value: 'macchiato', label: 'Catppuccin Macchiato' },
			{ value: 'mocha', label: 'Catppuccin Mocha' }
		]);

		await page.locator('select[name="custom-theme"]').selectOption('mocha');

		await page.locator('#section-theme button[class*="btn-primary"]').click();
		await page.waitForTimeout(1000);

		const saved = page.locator('#section-theme').getByText(/saved|gespeichert/i);
		await expect(saved).toBeVisible({ timeout: 5000 });

		const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
		expect(theme).toBe('mocha');

		const baseColor = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--color-base-100').trim()
		);
		expect(baseColor).toMatch(/#1e1e2e|rgb\(30, 30, 46\)/i);

		// The choice must survive a full reload from the stored profile settings.
		await page.reload();
		await page.waitForTimeout(1500);
		const reloadedTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
		expect(reloadedTheme).toBe('mocha');
		const reloadedBase = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--color-base-100').trim()
		);
		expect(reloadedBase).toMatch(/#1e1e2e|rgb\(30, 30, 46\)/i);

		// Light direction: Latte must keep the light favicon.
		await page.locator('select[name="custom-theme"]').selectOption('latte');
		await page.locator('#section-theme button[class*="btn-primary"]').click();
		await page.waitForTimeout(1000);
		const latteTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
		expect(latteTheme).toBe('latte');
		const favicon = await page.evaluate(
			() => document.querySelector('link[rel="icon"][type="image/svg+xml"]')?.getAttribute('href') ?? ''
		);
		expect(favicon).not.toContain('favicon-dark');
	});

	test('11.4 create api key', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		const addKeyBtn = page.locator('button').filter({ hasText: /add key/i }).first();
		if (await addKeyBtn.isVisible()) {
			await addKeyBtn.click();
			await page.waitForTimeout(1000);
			await expect(page.locator('body')).toContainText(/key|api/i);
		}
	});

	test('11.5 create embed token', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		await page.locator('#section-embed-tokens').scrollIntoViewIfNeeded();
		await page.waitForTimeout(500);

		const input = page.locator('input[name="embed-token-name"]');
		await input.fill('E2E Test Widget');
		await page.locator('#section-embed-tokens button.btn-primary').first().click();
		await page.waitForTimeout(1000);

		await expect(page.locator('#section-embed-tokens')).toContainText(/le_/);

		const tokenText = await page.locator('#section-embed-tokens div.font-mono.break-all').first().textContent();
		expect(tokenText).toBeTruthy();

		if (tokenText) {
			const backendHealthUrl = process.env.E2E_BACKEND_URL || 'http://backend:8000/api/health';
			const backendOrigin = new URL(backendHealthUrl).origin;
			const iframeUrl = `${backendOrigin}/embed/v1/stats?token=${tokenText.trim()}`;
			const resp = await page.request.get(iframeUrl);
			expect(resp.status()).toBe(200);
			const html = await resp.text();
			expect(html).toContain('Books');
			expect(html).toMatch(/^<!doctype html>/i);
		}
	});

	test('11.6 embed tokens section respects embed_enabled flag', async ({ page }) => {
		// Mock the config endpoint to simulate embed being disabled
		await page.route('**/api/config', async route => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					embed_enabled: false,
					dashboard_quote_enabled: true,
					thalia_cover_search_enabled: false,
					password_login_enabled: true,
					trusted_proxy_auth_enabled: false
				})
			});
		});

		await page.goto('/profile');
		await page.waitForTimeout(1000);

		// The embed tokens section should not exist in the DOM
		await expect(page.locator('#section-embed-tokens')).toHaveCount(0);

		// Remove the route override so next navigation uses real config
		await page.unroute('**/api/config');

		await page.goto('/profile');
		await page.waitForTimeout(1000);

		// Now the embed tokens section should be visible
		await expect(page.locator('#section-embed-tokens')).toBeVisible();
	});

	test('11.7 enable and configure reading goals', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		await page.locator('#section-goals').scrollIntoViewIfNeeded();
		await page.waitForTimeout(500);

		await page.locator('input[name="goal-pages-per-day-enabled"]').check();
		await page.locator('input[name="goal-pages-per-day"]').fill('25');
		await page.locator('input[name="goal-books-per-year-enabled"]').check();

		await page.locator('#section-goals button[class*="btn-primary"]').click();
		await page.waitForTimeout(1000);

		const alert = page.locator('#section-goals .alert');
		await expect(alert).toBeVisible({ timeout: 5000 });

		await page.reload();
		await page.waitForTimeout(1000);

		await expect(page.locator('input[name="goal-pages-per-day-enabled"]')).toBeChecked();
		await expect(page.locator('input[name="goal-pages-per-day"]')).toHaveValue('25');
		await expect(page.locator('input[name="goal-books-per-year-enabled"]')).toBeChecked();
	});

	test('11.8 goal input is disabled until enabled', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		await page.locator('#section-goals').scrollIntoViewIfNeeded();
		await page.waitForTimeout(500);

		const input = page.locator('input[name="goal-books-per-month"]');
		await expect(input).toBeDisabled();

		await page.locator('input[name="goal-books-per-month-enabled"]').check();
		await expect(input).toBeEnabled();
	});
});

test.describe('Profile picture', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('11.9 avatar section defaults to the animal avatar', async ({ page }) => {
		await page.goto('/profile');
		await page.locator('#section-avatar').scrollIntoViewIfNeeded();

		const sources = page.locator('#section-avatar input[name="avatar-source"]');
		await expect(sources).toHaveCount(3);
		await expect(sources.first()).toBeChecked();
		await expect(page.locator('#section-avatar button.btn-primary')).toBeVisible();
	});

	test('11.10 upload a cropped avatar and show it in the user menu', async ({ page }) => {
		await page.goto('/profile');
		await page.locator('#section-avatar').scrollIntoViewIfNeeded();

		await page.locator('#section-avatar input[type=file]').setInputFiles('e2e/fixtures/avatar.png');
		const dialog = page.locator('.modal.modal-open');
		await expect(dialog).toBeVisible();
		await expect(dialog).toContainText(/crop your picture|bild zuschneiden/i);

		await dialog.locator('button.btn-primary').click();
		await expect(page.locator('#section-avatar .alert')).toBeVisible({ timeout: 10000 });

		await expect(page.locator('button:has(img[src*="/api/users/"])').first()).toBeVisible();
	});
});

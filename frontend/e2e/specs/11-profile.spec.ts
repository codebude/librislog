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
					thalia_cover_search_enabled: false
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
});

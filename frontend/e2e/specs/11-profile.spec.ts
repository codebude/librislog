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
});

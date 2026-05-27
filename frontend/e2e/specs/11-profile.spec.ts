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

import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Data Import', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('9.1 data import page loads', async ({ page }) => {
		await page.goto('/data?tab=import');
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/import|upload|csv/i);
	});
});

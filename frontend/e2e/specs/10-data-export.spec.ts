import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Data Export', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('10.1 data export page loads', async ({ page }) => {
		await page.goto('/data');
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/export|csv|json|download/i);
	});
});

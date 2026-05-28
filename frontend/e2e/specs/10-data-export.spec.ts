import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Data Export', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('10.1 export page loads', async ({ page }) => {
		await page.goto('/data');
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/Export/i);
	});

	test('10.2 export downloads a file', async ({ page }) => {
		await page.goto('/data');
		await page.waitForTimeout(1000);

		const responsePromise = page.waitForResponse(
			(resp) => resp.url().includes('/data/export') && resp.status() === 200
		);

		await page.locator('button').filter({ hasText: 'Export data' }).click();

		const response = await responsePromise;
		expect(response.ok()).toBeTruthy();

		const contentType = response.headers()['content-type'] || '';
		expect(contentType).toContain('zip');
	});

	test('10.3 export with CSV format', async ({ page }) => {
		await page.goto('/data');
		await page.waitForTimeout(1000);

		await page.locator('input[type="radio"][value="csv"]').click();

		const responsePromise = page.waitForResponse(
			(resp) => resp.url().includes('/data/export') && resp.status() === 200
		);

		await page.locator('button').filter({ hasText: 'Export data' }).click();

		const response = await responsePromise;
		expect(response.ok()).toBeTruthy();
	});
});

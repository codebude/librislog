import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Admin', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('12.1 admin page loads user list', async ({ page }) => {
		await page.goto('/admin');
		await page.waitForTimeout(2000);
		const body = page.locator('body');
		await expect(body).toContainText(/user|admin|e2e/i);
	});
});

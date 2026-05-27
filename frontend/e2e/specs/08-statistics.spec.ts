import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';

test.describe('Statistics', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await deleteAllBooks(page);
		await seedBooks(page, SEED_BOOKS);
	});

	test('8.1 statistics page loads', async ({ page }) => {
		await page.goto('/statistics');
		await page.waitForTimeout(2000);
		const body = page.locator('body');
		await expect(body).toContainText(/total|books|pages|rating|read/i);
	});
});

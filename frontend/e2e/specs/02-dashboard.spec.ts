import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';

test.describe('Dashboard', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await page.goto('/dashboard');
		await page.waitForSelector('h1');
	});

	test('2.1 dashboard loads stats', async ({ page }) => {
		await seedBooks(page, SEED_BOOKS);
		await page.reload();
		await page.waitForSelector('h1');
		const body = page.locator('body');
		await expect(body).toContainText(/want to read|currently reading|total/i);
	});

	test('2.2 navigate to library via sidebar', async ({ page }) => {
		await page.click('a[href="/library"]');
		await expect(page).toHaveURL('/library');
	});

	test('2.3 navigate to timeline via sidebar', async ({ page }) => {
		await page.click('a[href="/timeline"]');
		await expect(page).toHaveURL('/timeline');
	});

	test('2.4 navigate to statistics via sidebar', async ({ page }) => {
		await page.click('a[href="/statistics"]');
		await expect(page).toHaveURL('/statistics');
	});
});

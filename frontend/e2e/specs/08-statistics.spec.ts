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

	test('8.2 rating statistics are displayed', async ({ page }) => {
		await page.goto('/statistics');
		await page.waitForTimeout(2000);

		await expect(page.getByText(/Books with Rating|Bewertete Bücher/)).toBeVisible();
		await expect(page.getByText(/Books without Rating|Unbewertete Bücher/)).toBeVisible();
		await expect(page.getByText(/Avg Rating|Ø Bewertung/)).toBeVisible();

		await expect(page.getByText(/Top Rated|Am besten bewertet/)).toBeVisible();
		await expect(page.getByText(/Worst Rated|Am schlechtesten bewertet/)).toBeVisible();

		await expect(page.getByText('To Kill a Mockingbird').first()).toBeVisible();
		await expect(page.getByText('1984').first()).toBeVisible();
		await expect(page.getByText('The Great Gatsby').first()).toBeVisible();
		await expect(page.getByText('Brave New World').first()).toBeVisible();
	});
});

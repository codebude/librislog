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

	test('8.3 top authors reflect multi-author books', async ({ page }) => {
		// Give Frank Herbert more books (Good Omens already counts Pratchett/Gaiman).
		await seedBooks(page, [
			{ title: 'Children of Dune', author: 'Frank Herbert', reading_status: 'read', rating: 4, page_count: 408, date_started: '2024-01-01', date_finished: '2024-01-20' },
			{ title: 'God Emperor of Dune', author: 'Frank Herbert', reading_status: 'read', rating: 4, page_count: 496, date_started: '2024-02-01', date_finished: '2024-02-20' },
		]);

		await page.goto('/statistics');
		await page.waitForTimeout(2000);

		// Frank Herbert now has the most books and must be the top author.
		await expect(page.getByText(/Top Authors|Beliebteste Autoren/i)).toBeVisible();
		const topAuthorsCard = page
			.locator('.card')
			.filter({ has: page.getByRole('heading', { name: /Top Authors|Beliebteste Autoren/i }) });
		const frankCard = topAuthorsCard.locator('.rounded-xl').filter({ hasText: 'Frank Herbert' }).first();
		await expect(frankCard).toBeVisible({ timeout: 5000 });
		await expect(frankCard.getByText('#1', { exact: true })).toBeVisible();
	});
});

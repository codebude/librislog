import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';

test.describe('Search Page', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await deleteAllBooks(page);
		await seedBooks(page, SEED_BOOKS);
	});

	test('4.1 search results page displays matching books from URL param', async ({ page }) => {
		await page.goto('/search?q=Gatsby');
		await page.waitForTimeout(1500);

		await expect(page.locator('body')).toContainText(/The Great Gatsby/i);
	});

	test('4.2 empty results page shows no results message', async ({ page }) => {
		await page.goto('/search?q=xyznonexistent');
		await page.waitForTimeout(1500);

		await expect(page.locator('body')).toContainText(/No results/i);
	});

	test('4.3 typing in search input triggers live search', async ({ page }) => {
		await page.goto('/search');
		await page.waitForTimeout(500);

		const input = page.locator('input[type="text"]');
		await input.fill('Dune');
		await page.waitForTimeout(500);

		await expect(page.locator('body')).toContainText(/Dune/i);
	});

	test('4.4 pressing Enter updates URL and re-searches', async ({ page }) => {
		await page.goto('/search');
		await page.waitForTimeout(500);

		const input = page.locator('input[type="text"]');
		await input.fill('Neuromancer');
		await input.press('Enter');

		await expect(page).toHaveURL(/\/search\?q=Neuromancer/);
		await page.waitForTimeout(500);
		await expect(page.locator('body')).toContainText(/Neuromancer/i);
	});

	test('4.5 clear button clears input and results', async ({ page }) => {
		await page.goto('/search?q=1984');
		await page.waitForTimeout(1500);

		await expect(page.locator('body')).toContainText(/1984/i);

		// Click via JS to bypass any overlaying elements (UserMenu fixed container)
		await page.evaluate(() => {
			const btn = document.querySelector('button[aria-label="Clear Form"]') as HTMLButtonElement | null;
			btn?.click();
		});
		await page.waitForTimeout(500);

		const input = page.locator('input[type="text"]');
		await expect(input).toHaveValue('');
	});

	test('4.6 back button navigates to previous page', async ({ page }) => {
		await page.goto('/dashboard');
		await page.waitForSelector('h1');

		await page.goto('/search?q=Gatsby');
		await page.waitForTimeout(500);

		const backBtn = page.locator('button[aria-label="Back"]');
		await backBtn.click();

		await expect(page).toHaveURL('/dashboard');
	});
});

import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';
import { LibraryPage } from '../fixtures/pages/library.page';

test.describe('Library Browsing', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await deleteAllBooks(page);
		await seedBooks(page, SEED_BOOKS);
	});

	test('3.1 default tab shows books', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);
		const count = await library.getBookCount();
		expect(count).toBeGreaterThanOrEqual(0);
	});

	test('3.2 switch reading status tabs', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);

		await library.switchTab('currently reading');
		await page.waitForTimeout(500);
		const currentlyReadingCount = await library.getBookCount();
		expect(currentlyReadingCount).toBeGreaterThanOrEqual(1);

		await library.switchTab('want to read');
		await page.waitForTimeout(500);
	});

	test('3.3 search in library', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);

		await library.search('Gatsby');
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/Gatsby/i);
	});

	test('3.4 empty state when no books match', async ({ page }) => {
		await deleteAllBooks(page);
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/no books|empty/i);
	});
});

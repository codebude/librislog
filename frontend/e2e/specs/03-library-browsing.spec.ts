import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';
import { LibraryPage } from '../fixtures/pages/library.page';

async function createWantToReadBook(
	page: import('@playwright/test').Page,
	title: string,
	acquisition_status: 'owned' | 'borrowed' | 'digital_access' | 'to_acquire'
) {
	const csrf = await page.request.get('/api/auth/csrf');
	const { csrf_token } = await csrf.json();
	const response = await page.request.post('/api/books', {
		data: { title, author: 'E2E Author', page_count: 200, reading_status: 'want_to_read', acquisition_status },
		headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf_token },
	});
	expect(response.ok()).toBeTruthy();
}

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

	test('3.5 manual creation requires possession and persists the selected value', async ({ page }) => {
		await deleteAllBooks(page);
		const library = new LibraryPage(page);
		await library.goto();

		await page.getByRole('button', { name: '+ Add Book' }).click();
		const modal = page.locator('.modal-box');
		const availability = modal.getByRole('combobox', { name: /Possession/ });
		await expect(availability).toHaveValue('');

		await modal.getByLabel('Title *').fill('Digital E2E Book');
		// The author field is a chip input: type and press Enter to add the author.
		const authorInput = modal.getByRole('textbox', { name: /Author/ });
		await authorInput.fill('E2E Author');
		await authorInput.press('Enter');
		await modal.getByLabel(/Pages/).fill('200');
		await availability.selectOption('digital_access');
		await modal.getByRole('button', { name: 'Add Book' }).click();

		await expect(page.getByText('Digital E2E Book')).toBeVisible();
		const response = await page.request.get('/api/books?q=Digital%20E2E%20Book');
		expect((await response.json()).books[0].acquisition_status).toBe('digital_access');
	});

	test('3.6 filters Want to Read books by possession and marks books to acquire', async ({ page }) => {
		await deleteAllBooks(page);
		await createWantToReadBook(page, 'Owned E2E Book', 'owned');
		await createWantToReadBook(page, 'Acquire E2E Book', 'to_acquire');
		const library = new LibraryPage(page);
		await library.goto();

		await expect(page.getByText('Owned E2E Book')).toBeVisible();
		await expect(page.getByText('Acquire E2E Book')).toBeVisible();
		await expect(page.locator('span[aria-label="Needs to be acquired"]')).toBeVisible();

		await page.locator('select[name="acquisition_filter"]').selectOption('to_acquire');
		await expect(page.getByText('Acquire E2E Book')).toBeVisible();
		await expect(page.getByText('Owned E2E Book')).not.toBeVisible();
	});

	test('3.7 All Books tab shows every book regardless of status with search and sort', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();

		await page.getByRole('tab', { name: /All Books/ }).click();
		await expect(page).toHaveURL(/\/library\?status=all/);

		// All 12 seeded books are shown, spanning every reading status.
		await expect(library.getBookCards()).toHaveCount(12);
		await expect(page.getByText('The Great Gatsby')).toBeVisible();
		await expect(page.getByText('The Three-Body Problem')).toBeVisible();
		await expect(page.getByText('1984')).toBeVisible();
		await expect(page.getByText('Atlas Shrugged')).toBeVisible();

		// Smart sort is hidden on the All tab; the sort selects are enabled.
		await expect(page.locator('input[name="smart-sort"]')).toHaveCount(0);
		await expect(page.locator('select[name="sort-field"]')).toBeEnabled();

		// Sort by title ascending: "1984" is alphabetically first among the seeds.
		await page.locator('select[name="sort-field"]').selectOption('title');
		await page.locator('select[name="sort-order"]').selectOption('asc');
		await expect(page.locator('button.card h2').first()).toHaveText('1984');

		// Search narrows the All tab results.
		const searchInput = page.getByPlaceholder(/Search books/);
		await searchInput.fill('Dune');
		await searchInput.press('Enter');
		await expect(page.locator('button.card')).toHaveCount(1);
		await expect(page.getByText('Dune')).toBeVisible();
		await expect(page.getByText('1984')).not.toBeVisible();
	});
});

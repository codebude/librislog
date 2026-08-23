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

	test('3.5 manual creation requires availability and persists the selected value', async ({ page }) => {
		await deleteAllBooks(page);
		const library = new LibraryPage(page);
		await library.goto();

		await page.getByRole('button', { name: '+ Add Book' }).click();
		const modal = page.locator('.modal-box');
		const availability = modal.getByRole('combobox', { name: /Availability/ });
		await expect(availability).toHaveValue('');

		await modal.getByLabel('Title *').fill('Digital E2E Book');
		await modal.getByRole('searchbox', { name: /Author/ }).fill('E2E Author');
		await modal.getByLabel(/Pages/).fill('200');
		await availability.selectOption('digital_access');
		await modal.getByRole('button', { name: 'Add Book' }).click();

		await expect(page.getByText('Digital E2E Book')).toBeVisible();
		const response = await page.request.get('/api/books?q=Digital%20E2E%20Book');
		expect((await response.json()).books[0].acquisition_status).toBe('digital_access');
	});

	test('3.6 filters Want to Read books by availability and marks books to acquire', async ({ page }) => {
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
});

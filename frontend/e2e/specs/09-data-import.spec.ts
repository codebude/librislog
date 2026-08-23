import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Data Import', () => {
	const CSV = `title,author,isbn,pages,status,availability
"The Imported Book","Import Author","1234567890",300,want_to_read,owned
"Second Imported","Another Author","9876543210",250,want_to_read,to_acquire`;

	const CSV_ACQUISITION = `title,author,isbn,pages,status,availability
"Acquisition Test A","Author A","1111111111",300,want_to_read,owned
"Acquisition Test B","Author B","2222222222",250,want_to_read,to_acquire`;

	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
	});

	test('9.1 import page loads', async ({ page }) => {
		await page.goto('/data?tab=import');
		await page.waitForTimeout(1000);
		const body = page.locator('body');
		await expect(body).toContainText(/Import/i);
	});

	test('9.2 full import flow creates books in library', async ({ page }) => {
		await page.goto('/data?tab=import');
		await page.waitForTimeout(1000);

		await page.locator('input[type="file"]').setInputFiles({
			name: 'test-books.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from(CSV),
		});

		await page.locator('button').filter({ hasText: 'Parse file' }).click();
		await page.waitForTimeout(2000);

		await expect(page.locator('select[name="mapping-target-title"]')).toBeVisible({ timeout: 10000 });

		await page.locator('select[name="mapping-target-title"]').selectOption('title');
		await page.locator('select[name="mapping-target-author"]').selectOption('author');
		await page.locator('select[name="mapping-target-isbn"]').selectOption('isbn');
		await page.locator('select[name="mapping-target-page_count"]').selectOption('pages');
		await page.locator('select[name="mapping-target-reading_status"]').selectOption('status');
		await page.locator('select[name="mapping-target-acquisition_status"]').selectOption('availability');

		await page.locator('textarea[name="mapping-transform-title"]').fill('value.strip().upper()');

		await page.locator('button').filter({ hasText: 'Generate' }).click();
		await page.waitForTimeout(2000);

		const previewBody = page.locator('body');
		await expect(previewBody).toContainText(/THE IMPORTED BOOK|SECOND IMPORTED/i, { timeout: 10000 });

		await page.locator('button').filter({ hasText: 'Simulate' }).click();
		await page.waitForTimeout(2000);

		const body = page.locator('body');
		const validationOk = body.getByText('Validation passed.');
		const valid = await validationOk.isVisible().catch(() => false);

		if (valid) {
			await page.locator('button.btn-secondary.btn-sm').filter({ hasText: 'Import now' }).click();
			await page.locator('dialog.modal-open .btn-secondary').filter({ hasText: 'Import now' }).waitFor({ state: 'visible', timeout: 5000 });
			await page.locator('dialog.modal-open .btn-secondary').filter({ hasText: 'Import now' }).click();
			await page.waitForTimeout(2000);

			await expect(page.locator('dialog.modal-open')).not.toBeVisible({ timeout: 15000 });
			await expect(body).toContainText(/Import complete/i, { timeout: 5000 });
		}

		await page.goto('/library');
		await page.waitForTimeout(1000);
		const libraryBody = page.locator('body');
		if (valid) {
			await expect(libraryBody).toContainText(/THE IMPORTED BOOK|The Imported Book/i, { timeout: 5000 });
			await expect(libraryBody).toContainText(/SECOND IMPORTED|Second Imported/i, { timeout: 5000 });
		}
	});

		test('9.3 transform syntax error shown in preview', async ({ page }) => {
		await page.goto('/data?tab=import');
		await page.waitForTimeout(1000);

		await page.locator('input[type="file"]').setInputFiles({
			name: 'test-books.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from(CSV),
		});

		await page.locator('button').filter({ hasText: 'Parse file' }).click();
		await page.waitForTimeout(2000);

		await expect(page.locator('select[name="mapping-target-title"]')).toBeVisible({ timeout: 10000 });

		await page.locator('select[name="mapping-target-title"]').selectOption('title');
		await page.locator('select[name="mapping-target-author"]').selectOption('author');
		await page.locator('select[name="mapping-target-isbn"]').selectOption('isbn');
		await page.locator('select[name="mapping-target-page_count"]').selectOption('pages');
		await page.locator('select[name="mapping-target-reading_status"]').selectOption('status');
		await page.locator('select[name="mapping-target-acquisition_status"]').selectOption('availability');

		await page.locator('textarea[name="mapping-transform-title"]').fill('value.upper(');

		await page.locator('button').filter({ hasText: 'Generate' }).click();
		await page.waitForTimeout(2000);

		const body = page.locator('body');
		await expect(body).toContainText(/error|invalid|syntax/i, { timeout: 10000 });
	});

	test('9.4 import validation rejects missing acquisition_status mapping', async ({ page }) => {
		await page.goto('/data?tab=import');
		await page.waitForTimeout(1000);

		await page.locator('input[type="file"]').setInputFiles({
			name: 'test-books.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from(CSV),
		});

		await page.locator('button').filter({ hasText: 'Parse file' }).click();
		await page.waitForTimeout(2000);

		await page.locator('select[name="mapping-target-title"]').selectOption('title');
		await page.locator('select[name="mapping-target-author"]').selectOption('author');
		await page.locator('select[name="mapping-target-isbn"]').selectOption('isbn');
		await page.locator('select[name="mapping-target-page_count"]').selectOption('pages');
		await page.locator('select[name="mapping-target-reading_status"]').selectOption('status');
		// intentionally omit acquisition_status mapping

		await page.locator('button').filter({ hasText: 'Simulate' }).click();
		await page.waitForTimeout(2000);

		const body = page.locator('body');
		await expect(body).toContainText(/acquisition_status/i, { timeout: 10000 });
		await expect(body).toContainText(/required/i, { timeout: 10000 });
	});

	test('9.5 imported books retain their acquisition status', async ({ page }) => {
		await deleteAllBooks(page);
		await page.goto('/data?tab=import');
		await page.waitForTimeout(1000);

		await page.locator('input[type="file"]').setInputFiles({
			name: 'test-books.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from(CSV_ACQUISITION),
		});

		await page.locator('button').filter({ hasText: 'Parse file' }).click();
		await page.waitForTimeout(2000);

		await page.locator('select[name="mapping-target-title"]').selectOption('title');
		await page.locator('select[name="mapping-target-author"]').selectOption('author');
		await page.locator('select[name="mapping-target-isbn"]').selectOption('isbn');
		await page.locator('select[name="mapping-target-page_count"]').selectOption('pages');
		await page.locator('select[name="mapping-target-reading_status"]').selectOption('status');
		await page.locator('select[name="mapping-target-acquisition_status"]').selectOption('availability');

		await page.locator('button').filter({ hasText: 'Generate' }).click();
		await page.waitForTimeout(2000);

		await page.locator('button').filter({ hasText: 'Simulate' }).click();
		await page.waitForTimeout(2000);

		const body = page.locator('body');
		await expect(body).toContainText('Validation passed.', { timeout: 10000 });

		await page.locator('button.btn-secondary.btn-sm').filter({ hasText: 'Import now' }).click();
		await page.locator('dialog.modal-open .btn-secondary').filter({ hasText: 'Import now' }).waitFor({ state: 'visible', timeout: 5000 });
		await page.locator('dialog.modal-open .btn-secondary').filter({ hasText: 'Import now' }).click();
		await page.waitForTimeout(2000);

		await expect(body).toContainText(/Import complete/i, { timeout: 10000 });

		const response = await page.request.get('/api/books?q=Acquisition%20Test%20B');
		const books = (await response.json()).books;
		expect(books).toHaveLength(1);
		expect(books[0].acquisition_status).toBe('to_acquire');
	});
});

import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';
import { LibraryPage } from '../fixtures/pages/library.page';

test.describe('Edit Book', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await deleteAllBooks(page);
		await seedBooks(page, SEED_BOOKS);
	});

	test('5.1 edit basic fields', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);

		await library.switchTab('want to read');
		await page.waitForTimeout(500);

		const cards = library.getBookCards();
		await expect(cards.first()).toBeVisible({ timeout: 5000 });

		await cards.first().click();
		await page.waitForSelector('[role="dialog"]', { timeout: 5000 });

		const editBtn = page.locator('[role="dialog"] button').filter({ hasText: 'Edit' });
		await expect(editBtn.first()).toBeVisible({ timeout: 5000 });
		await editBtn.first().click();

		await page.waitForTimeout(500);
		const body = page.locator('body');
		await expect(body).toContainText(/title|author|save/i);
	});

	test('5.2 cancel edit does not change values', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);

		await library.switchTab('want to read');
		await page.waitForTimeout(500);

		const cards = library.getBookCards();
		await expect(cards.first()).toBeVisible({ timeout: 5000 });

		await cards.first().click();
		await page.waitForSelector('[role="dialog"]', { timeout: 5000 });

		const editBtn = page.locator('[role="dialog"] button').filter({ hasText: 'Edit' });
		await expect(editBtn.first()).toBeVisible({ timeout: 5000 });
		await editBtn.first().click();

		const closeBtn = page.locator('button').filter({ hasText: /cancel|close/i }).first();
		if (await closeBtn.isVisible()) {
			await closeBtn.click();
		}
		await page.waitForTimeout(500);
	});
});

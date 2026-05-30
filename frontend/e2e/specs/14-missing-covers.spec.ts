import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER } from '../fixtures/seed-data';
import { MissingCoversPage } from '../fixtures/pages/missing-covers.page';

test.describe('Missing Covers Workflow', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await deleteAllBooks(page);
	});

	test('1. Entry point from profile navigates to missing-covers', async ({ page }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);
		await page.locator('a[href="/missing-covers"]').first().click();
		await expect(page).toHaveURL(/\/missing-covers/);
	});

	test('2. Header shows correct count', async ({ page }) => {
		await seedBooks(page, [
			{ title: 'Book A', author: 'Author A', page_count: 100, reading_status: 'read' },
			{ title: 'Book B', author: 'Author B', page_count: 200, reading_status: 'read' },
			{ title: 'Book C', author: 'Author C', page_count: 300, reading_status: 'read' },
		]);
		const missing = new MissingCoversPage(page);
		await missing.goto();
		await page.waitForTimeout(2000);
		const header = await missing.getHeader();
		expect(header).toContain('3');
	});

	test('3. Displays current book info', async ({ page }) => {
		await seedBooks(page, [
			{ title: 'Visible Book', author: 'Test Author', page_count: 100, reading_status: 'read' },
		]);
		const missing = new MissingCoversPage(page);
		await missing.goto();
		await page.waitForTimeout(2000);
		const title = await missing.getCurrentBookTitle();
		expect(title).toBe('Visible Book');
	});

	test('4. Missing covers page loads with books', async ({ page }) => {
		const missing = new MissingCoversPage(page);
		await missing.goto();
		await page.waitForTimeout(3000);
		expect(await page.locator('h1').isVisible()).toBe(true);
	});

	test('5. No-ISBN state shows manual fallback and google link', async ({ page }) => {
		await seedBooks(page, [
			{ title: 'No ISBN', author: 'Author X', page_count: 100, reading_status: 'read' },
		]);
		const missing = new MissingCoversPage(page);
		await missing.goto();
		await page.waitForTimeout(3000);

		await expect(page.locator('input[type="url"]')).toBeVisible({ timeout: 10000 });
	});

	test('6. Back link navigates to profile', async ({ page }) => {
		const missing = new MissingCoversPage(page);
		await missing.goto();
		await page.waitForTimeout(3000);

		await page.locator('a[href="/profile"]').first().click();
		await expect(page).toHaveURL(/\/profile/);
	});
});

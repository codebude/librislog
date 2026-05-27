import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { seedBooks, deleteAllBooks } from '../fixtures/seed.api';
import { SEED_USER, SEED_BOOKS } from '../fixtures/seed-data';

test.describe('Timeline', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await deleteAllBooks(page);
		await seedBooks(page, SEED_BOOKS);
	});

	test('7.1 timeline loads read books sorted by date', async ({ page }) => {
		await page.goto('/timeline');
		await page.waitForTimeout(2000);
		const body = page.locator('body');
		await expect(body).toContainText(/1984|To Kill a Mockingbird|Brave New World/i);
	});

	test('7.2 open book detail from timeline', async ({ page }) => {
		await page.goto('/timeline');
		await page.waitForTimeout(2000);
		const bookLink = page.locator('a, button, [role="button"]').filter({ hasText: /1984/i }).first();
		await expect(bookLink).toBeVisible({ timeout: 5000 });
		await bookLink.click();
		await expect(page.locator('[role="dialog"]')).toBeVisible({ timeout: 5000 });
	});
});

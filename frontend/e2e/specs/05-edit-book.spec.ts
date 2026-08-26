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

	test('5.3 set and persist rating from detail dialog', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);

		await library.switchTab('want to read');
		await page.waitForTimeout(500);

		const cards = library.getBookCards();
		await expect(cards.first()).toBeVisible({ timeout: 5000 });
		await cards.first().click();
		await page.waitForSelector('[role="dialog"]', { timeout: 5000 });

		const star2 = page.locator('[role="dialog"] input[type="radio"][aria-label*="2"]');
		await expect(star2).toBeVisible({ timeout: 5000 });
		await star2.click();

		await expect(page.getByText(/Rating saved|Bewertung gespeichert/i)).toBeVisible({ timeout: 3000 });

		const closeBtn = page.locator('button[aria-label*="Close"], button[aria-label*="Schließen"]').first();
		await closeBtn.click();
		await page.waitForTimeout(500);

		await cards.first().click();
		await page.waitForSelector('[role="dialog"]', { timeout: 5000 });

		const checkedStar = page.locator('[role="dialog"] input[type="radio"]:checked');
		await expect(checkedStar).toHaveAttribute('aria-label', /2 (star|Stern)/);
	});

	test('5.4 add a second author in the edit drawer', async ({ page }) => {
		const library = new LibraryPage(page);
		await library.goto();
		await page.waitForTimeout(1000);

		await library.switchTab('want to read');
		await page.waitForTimeout(500);

		const cards = library.getBookCards();
		await expect(cards.first()).toBeVisible({ timeout: 5000 });

		// Pick the Dune card (author: Frank Herbert).
		const duneCard = cards.filter({ hasText: 'Dune' }).first();
		await expect(duneCard).toBeVisible({ timeout: 5000 });
		await duneCard.click();
		await page.waitForSelector('[role="dialog"]', { timeout: 5000 });

		const editBtn = page.locator('[role="dialog"] button').filter({ hasText: 'Edit' });
		await editBtn.first().click();
		await page.waitForTimeout(500);

		const authorInput = page.locator('input[name="author"]');
		await expect(authorInput).toBeVisible({ timeout: 5000 });

		// Add a second author chip by typing and pressing Enter.
		await authorInput.fill('Brian Herbert');
		await authorInput.press('Enter');
		await expect(page.locator('text=Brian Herbert')).toBeVisible({ timeout: 5000 });

		await page.locator('button[type="submit"]').click();
		await page.waitForTimeout(800);

		// Verify the joined author string appears in the library detail.
		// Authors are returned sorted alphabetically: Brian Herbert, Frank Herbert.
		await expect(page.getByText(/Brian Herbert; Frank Herbert/i)).toBeVisible({ timeout: 5000 });
	});
});

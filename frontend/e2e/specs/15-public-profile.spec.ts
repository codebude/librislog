import { test, expect, type Browser, type Page } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';
import { seedBooks } from '../fixtures/seed.api';

async function createShareLink(
	page: Page,
	name: string,
	options: { sections?: string[]; language?: string } = {}
) {
	const section = page.locator('#section-share-profile');
	await section.scrollIntoViewIfNeeded();
	await page.waitForTimeout(500);

	await section.locator('button.btn-primary').click();

	const dialog = page.getByRole('dialog');
	await expect(dialog).toBeVisible();

	await dialog.locator('input[name="share-link-name"]').fill(name);

	if (options.sections) {
		for (const sectionKey of options.sections) {
			await dialog.locator(`input[name="share-link-section"][value="${sectionKey}"]`).check();
		}
	}

	if (options.language) {
		await dialog.locator('select[name="share-link-language"]').selectOption(options.language);
	}

	await dialog.locator('button[type="submit"]').click();
	await expect(dialog).not.toBeVisible();

	const urlText = await page.locator('#section-share-profile div.font-mono.break-all').first().textContent();
	expect(urlText).toMatch(/\/p\/lp_/);
	return urlText!.trim();
}

async function openIncognito(browser: Browser, url: string): Promise<Page> {
	const context = await browser.newContext();
	const publicPage = await context.newPage();
	await publicPage.goto(url);
	await publicPage.waitForLoadState('networkidle');
	return publicPage;
}

test.describe('Public Profile', () => {
	test.beforeEach(async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);

		// The shared E2E database may have German persisted from spec 11.2. Force English so
		// all assertions below are deterministic regardless of test order.
		await page.goto('/profile');
		await page.waitForTimeout(1500);
		await page.locator('select[name="language"]').selectOption('en');
		await page.locator('#section-language button[class*="btn-primary"]').click();
		await page.waitForTimeout(1000);
	});

	test('15.1 share link page shows selected sections and hides app chrome', async ({ page, browser }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		// Spec 14 wipes the seed library; seed a couple of books so the configured
		// sections (currently reading, full library + statistics) render real content
		// on the public page.
		await seedBooks(page, [
			{ title: '1984', author: 'George Orwell', page_count: 328, reading_status: 'read', date_started: '2024-10-01', date_finished: '2024-10-20' },
			{ title: 'The Three-Body Problem', author: 'Liu Cixin', page_count: 400, reading_status: 'currently_reading', date_started: '2025-01-15' }
		]);

		const shareUrl = await createShareLink(page, 'E2E Public Profile', {
			sections: ['full_library']
		});

		// The list entry persists the configured audience badge (default: Everyone)
		await expect(page.locator('#section-share-profile')).toContainText('E2E Public Profile');

		// App chrome (sidebar) is hidden on the public page even for logged-in users
		await page.goto(shareUrl);
		await page.waitForLoadState('networkidle');
		await expect(page.locator('aside')).toHaveCount(0);

		// Anonymous visitor sees the owner name, enabled sections, and no chrome
		const publicPage = await openIncognito(browser, shareUrl);
		await expect(publicPage.getByRole('heading', { name: /E2E Tester/ })).toBeVisible();
		await expect(publicPage.locator('aside')).toHaveCount(0);

		// full_library was selected explicitly and its content renders. Earlier specs
		// may leave duplicate copies of the same title in the shared E2E DB, so
		// assert presence (first match) rather than uniqueness.
		await expect(publicPage.getByText('Full Library')).toBeVisible();
		const librarySection = publicPage.locator('section').filter({ hasText: 'Full Library' });
		await expect(librarySection.locator('.grid > div')).not.toHaveCount(0);
		await expect(librarySection.getByText('1984', { exact: true }).first()).toBeVisible();

		// currently_reading is on by default and renders the started-on date
		const readingSection = publicPage.locator('section').filter({ hasText: 'Currently Reading' });
		await expect(readingSection.getByText('The Three-Body Problem', { exact: true }).first()).toBeVisible();
		await expect(readingSection.getByText('Started on', { exact: false }).first()).toBeVisible();

		// statistics section is on by default and shows computed values
		await expect(publicPage.getByText('Total Books')).toBeVisible();

		// footer links the librislog word to GitHub and nothing else
		const footer = publicPage.locator('footer');
		await expect(footer.getByRole('link', { name: 'LibrisLog' })).toBeVisible();
		await expect(footer.getByRole('link')).toHaveCount(1);
		await publicPage.close();
	});

	test('15.2 authenticated audience blocks anonymous viewers', async ({ page, browser }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		const shareUrl = await createShareLink(page, 'Audience Test');

		// Open the edit dialog and restrict access to logged-in users
		const row = page.locator('#section-share-profile li').filter({ hasText: 'Audience Test' });
		await row.locator('button[aria-label="Edit"]').click();
		const dialog = page.getByRole('dialog');
		await expect(dialog).toBeVisible();
		await dialog.locator('input[name="share-link-audience"][value="authenticated"]').check();
		await dialog.locator('button[type="submit"]').click();
		await expect(dialog).not.toBeVisible();

		await expect(row).toContainText('Logged-in users only');

		// A logged-in viewer can still open the page
		await page.goto(shareUrl);
		await page.waitForLoadState('networkidle');
		await expect(page.locator('h1')).toBeVisible();

		// Anonymous visitors are redirected to login
		const publicPage = await openIncognito(browser, shareUrl);
		await expect(publicPage.getByRole('heading', { name: 'Login required' })).toBeVisible();
		await expect(publicPage.getByRole('link', { name: 'Log in' })).toBeVisible();
		await publicPage.close();
	});

	test('15.3 deleted share link returns not found', async ({ page, browser }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		const shareUrl = await createShareLink(page, 'Delete Me Test');

		const row = page.locator('#section-share-profile li').filter({ hasText: 'Delete Me Test' });
		await row.locator('button[aria-label="Delete"]').click();

		const confirmDialog = page.locator('dialog.modal-open');
		await expect(confirmDialog).toBeVisible();
		await confirmDialog.locator('button.btn-error').click();
		await expect(confirmDialog).not.toBeVisible();

		// The deleted link's row disappears from the list
		await expect(page.locator('#section-share-profile li').filter({ hasText: 'Delete Me Test' })).toHaveCount(0);

		const publicPage = await openIncognito(browser, shareUrl);
		await expect(publicPage.getByText('This public profile link is no longer valid.')).toBeVisible();
		await publicPage.close();
	});

	test('15.4 share link language controls the public page locale', async ({ page, browser }) => {
		await page.goto('/profile');
		await page.waitForTimeout(1000);

		await seedBooks(page, [
			{ title: '1984', author: 'George Orwell', page_count: 328, reading_status: 'currently_reading', date_started: '2024-10-01' }
		]);

		const shareUrl = await createShareLink(page, 'German Profile Link', { language: 'de' });

		// Default language of the dialog follows the profile language ('en'); a German
		// share link renders the public page entirely in German for anonymous viewers.
		const publicPage = await openIncognito(browser, shareUrl);
		await expect(publicPage.getByText('Aktuell gelesen')).toBeVisible();
		await expect(publicPage.getByText('Currently Reading')).toHaveCount(0);
		await publicPage.close();

		const dialog = page.getByRole('dialog');
		await page.locator('#section-share-profile').scrollIntoViewIfNeeded();
		await page.waitForTimeout(500);
		const row = page.locator('#section-share-profile li').filter({ hasText: 'German Profile Link' });
		await row.locator('button[aria-label="Edit"]').click();
		await expect(dialog).toBeVisible();
		await expect(dialog.locator('select[name="share-link-language"]')).toHaveValue('de');
		await dialog.locator('button[aria-label="Close"]').click();
	});
});
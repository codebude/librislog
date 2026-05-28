import { test, expect } from '@playwright/test';
import { LoginPage } from '../fixtures/pages/login.page';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Setup & Login', () => {
	test('1.1 first-time setup flow creates admin and lands on dashboard', async ({ page }) => {
		const resp = await page.request.get('/api/auth/setup-required');
		const { required } = await resp.json();
		test.skip(!required, 'Setup already completed — skipping');

		await page.goto('/setup');
		await expect(page.locator('h1')).toBeVisible();

		await page.fill('input[autocomplete="given-name"]', SEED_USER.firstname);
		await page.fill('input[autocomplete="family-name"]', SEED_USER.lastname);
		await page.fill('input[type="email"]', SEED_USER.email);
		await page.fill('input[autocomplete="new-password"]', SEED_USER.password);
		await page.click('button[type="submit"]');

		await page.waitForURL(/\/(dashboard|library)/);
		await expect(page.locator('h1')).toBeVisible();
	});

	test('1.2 login with valid credentials', async ({ page }) => {
		const loginPage = new LoginPage(page);
		await loginPage.goto();
		await loginPage.login(SEED_USER.email, SEED_USER.password);
		await expect(page.locator('h1')).toBeVisible();
	});

	test('1.3 login with wrong password shows error', async ({ page }) => {
		const loginPage = new LoginPage(page);
		await loginPage.goto();
		await page.fill('input[type="email"]', SEED_USER.email);
		await page.fill('input[type="password"]', 'wrongpassword');
		await page.click('button[type="submit"]');
		await expect(page.locator('[role="alert"]')).toBeVisible();
		await expect(page).toHaveURL(/\/login/);
	});

	test('1.4 unauthenticated user is redirected to login', async ({ page }) => {
		await page.goto('/library');
		await expect(page).toHaveURL(/\/login/);
	});

	test('1.5 setup redirects to dashboard when already set up', async ({ page }) => {
		const resp = await page.request.get('/api/auth/setup-required');
		const { required } = await resp.json();
		test.skip(required, 'Setup not yet completed — skipping');

		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await page.goto('/setup');
		await expect(page).toHaveURL(/\/(dashboard|library)/);
	});
});

import { test, expect } from '@playwright/test';
import { loginViaUi } from '../fixtures/auth.fixture';
import { SEED_USER } from '../fixtures/seed-data';

test.describe('Logout', () => {
	test('13.1 logout from usermenu', async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		const menuButton = page.locator('button.btn-circle').first();
		await menuButton.click();
		await page.waitForTimeout(300);
		const logoutButton = page.getByRole('button', { name: /logout|abmelden/i });
		await logoutButton.click();
		await page.waitForURL(/\/login/);
	});

	test('13.2 cannot access protected pages after logout', async ({ page }) => {
		await loginViaUi(page, SEED_USER.email, SEED_USER.password);
		await page.context().clearCookies();
		await page.goto('/library');
		await expect(page).toHaveURL(/\/login/);
	});
});

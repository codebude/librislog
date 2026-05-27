import type { Page } from '@playwright/test';

export async function loginViaUi(page: Page, email: string, password: string): Promise<void> {
	await page.goto('/login');
	await page.waitForLoadState('networkidle');
	await page.fill('input[type="email"]', email);
	await page.fill('input[type="password"]', password);
	await page.click('button[type="submit"]');
	await page.waitForURL(/\/(dashboard|library)/);
}

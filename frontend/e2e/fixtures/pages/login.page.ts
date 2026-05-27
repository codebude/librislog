import type { Page } from '@playwright/test';

export class LoginPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto('/login');
		await this.page.waitForSelector('h1');
	}

	async login(email: string, password: string) {
		await this.page.fill('input[type="email"]', email);
		await this.page.fill('input[type="password"]', password);
		await this.page.click('button[type="submit"]');
		await this.page.waitForURL(/\/(dashboard|library)/);
	}

	async getErrorMessage() {
		const alert = this.page.locator('[role="alert"]');
		const text = await alert.textContent();
		return text ?? null;
	}
}

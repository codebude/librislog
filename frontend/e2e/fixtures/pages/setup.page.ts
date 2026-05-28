import type { Page } from '@playwright/test';

export class SetupPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto('/setup');
		await this.page.waitForSelector('h1');
	}

	async setupAdmin(firstname: string, lastname: string, email: string, password: string) {
		await this.page.fill('input[autocomplete="given-name"]', firstname);
		await this.page.fill('input[autocomplete="family-name"]', lastname);
		await this.page.fill('input[type="email"]', email);
		await this.page.fill('input[autocomplete="new-password"]', password);
		await this.page.click('button[type="submit"]');
		await this.page.waitForURL(/\/(dashboard|library)/);
	}
}

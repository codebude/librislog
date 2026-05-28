import type { Page, Locator } from '@playwright/test';

export class LibraryPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto('/library');
		await this.page.waitForSelector('h1');
	}

	async switchTab(status: string) {
		const tab = this.page.locator(`[role="tab"]`).filter({ hasText: new RegExp(status, 'i') });
		await tab.click();
		await this.page.waitForTimeout(500);
	}

	getBookCards(): Locator {
		return this.page.locator('button.card');
	}

	async getBookCount(): Promise<number> {
		return this.getBookCards().count();
	}

	async openBookDetail(title: string) {
		await this.page.locator(`text="${title}"`).first().click();
		await this.page.waitForSelector('[role="dialog"]');
	}

	async search(query: string) {
		const searchInput = this.page.locator('input[type="search"], input[placeholder*="Search"]').first();
		await searchInput.fill(query);
		await this.page.waitForTimeout(500);
	}
}

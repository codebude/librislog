import type { Page, Locator } from '@playwright/test';

export class LibraryPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto('/library');
		await this.page.waitForSelector('h1');
	}

	async switchTab(status: string) {
		const STATUS_ORDER: Record<string, number> = {
			'want to read': 0,
			'currently reading': 1,
			'read': 2,
			'did not finish': 3,
		};
		const key = status.toLowerCase().replace(/\s+/g, '_');
		const posMap: Record<string, number> = {
			'want_to_read': 0,
			'currently_reading': 1,
			'read': 2,
			'did_not_finish': 3,
		};
		const index = posMap[key] ?? STATUS_ORDER[status.toLowerCase()];
		if (index === undefined) {
			throw new Error(`Unknown tab status: ${status}`);
		}
		const tab = this.page.locator('[role="tab"]').nth(index);
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

import type { Page } from '@playwright/test';

export class DashboardPage {
	constructor(private page: Page) {}

	async goto() {
		await this.page.goto('/dashboard');
		await this.page.waitForSelector('h1');
	}

	async navigateToLibrary() {
		await this.page.click('a[href="/library"]');
		await this.page.waitForURL('/library');
	}

	async navigateToTimeline() {
		await this.page.click('a[href="/timeline"]');
		await this.page.waitForURL('/timeline');
	}

	async navigateToStatistics() {
		await this.page.click('a[href="/statistics"]');
		await this.page.waitForURL('/statistics');
	}

	async getHeading() {
		return this.page.locator('h1').textContent();
	}
}

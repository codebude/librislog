import type { Page } from '@playwright/test';

export class BookDrawerPage {
	constructor(private page: Page) {}

	async waitForDrawer() {
		await this.page.waitForTimeout(500);
	}

	async fillTitle(title: string) {
		const input = this.page.locator('input[name="title"], input[placeholder*="Title"]').first();
		await input.fill(title);
	}

	async fillAuthor(author: string) {
		const input = this.page.locator('input[name="author"], input[placeholder*="Author"]').first();
		await input.fill(author);
	}

	async clickSave() {
		const saveBtn = this.page.locator('button').filter({ hasText: /save/i }).first();
		await saveBtn.click();
		await this.page.waitForTimeout(500);
	}

	async close() {
		const closeBtn = this.page.locator('button').filter({ hasText: /cancel|close/i }).first();
		if (await closeBtn.isVisible()) {
			await closeBtn.click();
		}
	}
}

import type { Page } from '@playwright/test';

export class AddBookModalPage {
	constructor(private page: Page) {}

	async open() {
		await this.page.locator('button').filter({ hasText: /add book/i }).first().click();
		await this.page.waitForTimeout(500);
	}

	async fillTitle(title: string) {
		const input = this.page.locator('[role="dialog"] input[name="title"], [role="dialog"] input[placeholder*="Title"]').first();
		await input.fill(title);
	}

	async fillAuthor(author: string) {
		const input = this.page.locator('[role="dialog"] input[name="author"], [role="dialog"] input[placeholder*="Author"]').first();
		await input.fill(author);
	}

	async clickSave() {
		await this.page.locator('[role="dialog"] button[type="submit"]').first().click();
		await this.page.waitForTimeout(500);
	}
}

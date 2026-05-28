import type { Page } from '@playwright/test';

export class BookDetailPage {
	constructor(private page: Page) {}

	async waitForDialog() {
		await this.page.waitForSelector('[role="dialog"]');
	}

	async clickEdit() {
		const editBtn = this.page.locator('[role="dialog"] button, [role="dialog"] a')
			.filter({ hasText: /edit/i }).first();
		await editBtn.click();
	}

	async clickDelete() {
		const deleteBtn = this.page.locator('[role="dialog"] button, [role="dialog"] a')
			.filter({ hasText: /delete/i }).first();
		await deleteBtn.click();
	}

	async confirmDelete() {
		const confirmBtn = this.page.locator('[role="dialog"] button, [role="alertdialog"] button')
			.filter({ hasText: /confirm|delete|yes/i }).first();
		if (await confirmBtn.isVisible()) {
			await confirmBtn.click();
		}
	}

	async getTitle() {
		return this.page.locator('[role="dialog"] h2, [role="dialog"] h3').first().textContent();
	}
}

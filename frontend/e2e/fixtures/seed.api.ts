import type { Page } from '@playwright/test';
import type { SeedBook } from './seed-data';

function bookApiPath(): string {
	return '/api/books';
}

function csrfPath(): string {
	return '/api/auth/csrf';
}

async function getCsrfToken(page: Page): Promise<string> {
	const resp = await page.request.get(csrfPath());
	const { csrf_token } = await resp.json();
	return csrf_token;
}

export async function seedBooks(page: Page, books: SeedBook[]): Promise<void> {
	for (const book of books) {
		const csrf = await getCsrfToken(page);
		await page.request.post(bookApiPath(), {
			data: book,
			headers: {
				'Content-Type': 'application/json',
				'X-CSRF-Token': csrf,
			},
		});
	}
}

export async function deleteAllBooks(page: Page): Promise<void> {
	const resp = await page.request.get(bookApiPath() + '?limit=200');
	const body = await resp.json();
	const books: { id: number }[] = body.books;
	for (const book of books) {
		const csrf = await getCsrfToken(page);
		await page.request.delete(`${bookApiPath()}/${book.id}`, {
			headers: { 'X-CSRF-Token': csrf },
		});
	}
}

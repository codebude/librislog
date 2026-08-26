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
		const resp = await page.request.post(bookApiPath(), {
			data: book,
			headers: {
				'Content-Type': 'application/json',
				'X-CSRF-Token': csrf,
			},
		});
		// 409 = book already seeded by an earlier test in this suite; that's fine.
		if (!resp.ok() && resp.status() !== 409) {
			throw new Error(`Seeding book "${book.title}" failed: ${resp.status()} ${await resp.text()}`);
		}
	}
}

export async function deleteAllBooks(page: Page): Promise<void> {
	const resp = await page.request.get(bookApiPath() + '?limit=200');
	const body = await resp.json();
	const books: { id: number }[] = Array.isArray(body?.books) ? body.books : [];
	for (const book of books) {
		const csrf = await getCsrfToken(page);
		await page.request.delete(`${bookApiPath()}/${book.id}`, {
			headers: { 'X-CSRF-Token': csrf },
		});
	}
}

export async function getBookId(page: Page, title: string): Promise<number> {
	const resp = await page.request.get(`${bookApiPath()}?q=${encodeURIComponent(title)}&limit=20`);
	const body = await resp.json();
	const books: { id: number; title: string }[] = Array.isArray(body?.books) ? body.books : [];
	const book = books.find((b) => b.title === title);
	if (!book) throw new Error(`Book "${title}" not found`);
	return book.id;
}

export async function seedProgress(page: Page, bookId: number, pageNo: number): Promise<void> {
	const csrf = await getCsrfToken(page);
	const resp = await page.request.post(`${bookApiPath()}/${bookId}/progress`, {
		data: { page: pageNo },
		headers: {
			'Content-Type': 'application/json',
			'X-CSRF-Token': csrf,
		},
	});
	if (!resp.ok()) {
		throw new Error(`Seeding progress failed: ${resp.status()} ${await resp.text()}`);
	}
}

export async function updateProfileSettings(page: Page, data: Record<string, unknown>): Promise<void> {
	const csrf = await getCsrfToken(page);
	const resp = await page.request.patch('/api/profile/settings', {
		data,
		headers: {
			'Content-Type': 'application/json',
			'X-CSRF-Token': csrf,
		},
	});
	if (!resp.ok()) {
		throw new Error(`Updating profile settings failed: ${resp.status()} ${await resp.text()}`);
	}
}

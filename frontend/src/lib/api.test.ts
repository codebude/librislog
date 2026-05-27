import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { apiKey, csrfToken } from './stores/auth';

describe('api.covers.upload', () => {
	afterEach(() => {
		apiKey.set(null);
		csrfToken.set(null);
		vi.restoreAllMocks();
	});

	it('sends csrf token and same-origin credentials', async () => {
		apiKey.set('test-api-key');
		csrfToken.set('test-csrf-token');

		const fetchMock = vi
			.spyOn(globalThis, 'fetch')
			.mockResolvedValue({
				ok: true,
				json: async () => ({ cover_url: '/api/covers/uploaded.jpg' })
			} as Response);

		const file = new File(['fake-image-bytes'], 'cover.jpg', { type: 'image/jpeg' });
		const coverUrl = await api.covers.upload(file);

		expect(coverUrl).toBe('/api/covers/uploaded.jpg');
		expect(fetchMock).toHaveBeenCalledTimes(1);

		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.method).toBe('POST');
		expect(init.credentials).toBe('same-origin');
		expect(init.headers).toMatchObject({
			'X-API-Key': 'test-api-key',
			'X-CSRF-Token': 'test-csrf-token'
		});
		expect(init.body).toBeInstanceOf(FormData);
	});
});

describe('api.books.list', () => {
	beforeEach(() => {
		apiKey.set(null);
		csrfToken.set(null);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('returns { books, total } shape', async () => {
		const mockResponse = {
			books: [
				{ id: 1, title: 'Dune', author: 'Frank Herbert', reading_status: 'read' as const, date_added: '2024-01-01T00:00:00Z' },
			],
			total: 42,
		};

		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: { get: () => 'application/json' },
			json: async () => mockResponse,
		} as Response);

		const result = await api.books.list();

		expect(result).toHaveProperty('books');
		expect(result).toHaveProperty('total');
		expect(Array.isArray(result.books)).toBe(true);
		expect(result.total).toBe(42);
		expect(result.books).toHaveLength(1);
		expect(result.books[0].title).toBe('Dune');
	});

	it('returns empty books array and zero total when no books', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: { get: () => 'application/json' },
			json: async () => ({ books: [], total: 0 }),
		} as Response);

		const result = await api.books.list();

		expect(result.books).toEqual([]);
		expect(result.total).toBe(0);
	});

	it('passes query parameters correctly', async () => {
		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: { get: () => 'application/json' },
			json: async () => ({ books: [], total: 0 }),
		} as Response);

		await api.books.list({ status: 'read', q: 'dune', sort: 'title', order: 'asc' });

		const [url] = fetchMock.mock.calls[0] as [string];
		expect(url).toContain('status=read');
		expect(url).toContain('q=dune');
		expect(url).toContain('sort=title');
		expect(url).toContain('order=asc');
	});

	it('omits empty search query from URL', async () => {
		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: { get: () => 'application/json' },
			json: async () => ({ books: [], total: 0 }),
		} as Response);

		await api.books.list({ q: '' });

		const [url] = fetchMock.mock.calls[0] as [string];
		expect(url).not.toContain('q=');
	});
});

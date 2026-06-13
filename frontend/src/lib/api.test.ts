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
			} as unknown as Response);

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
		} as unknown as Response);

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
		} as unknown as Response);

		const result = await api.books.list();

		expect(result.books).toEqual([]);
		expect(result.total).toBe(0);
	});

	it('passes query parameters correctly', async () => {
		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: { get: () => 'application/json' },
			json: async () => ({ books: [], total: 0 }),
		} as unknown as Response);

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
		} as unknown as Response);

		await api.books.list({ q: '' });

		const [url] = fetchMock.mock.calls[0] as [string];
		expect(url).not.toContain('q=');
	});
});

describe('api.profile.embedTokens', () => {
	afterEach(() => {
		apiKey.set(null);
		csrfToken.set(null);
		vi.restoreAllMocks();
	});

	const mockHeaders = { get: () => 'application/json' };

	it('listEmbedTokens calls GET /profile/embed-tokens', async () => {
		apiKey.set('test-key');
		csrfToken.set('test-csrf');

		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: mockHeaders,
			json: async () => [{ id: 1, name: 'Test', token_prefix: 'le_abc', scopes: 'embed:stats:read', allowed_origins: null, expires_at: null, last_used_at: null, created_at: '2024-01-01T00:00:00Z' }]
		} as unknown as Response);

		const result = await api.profile.listEmbedTokens();
		expect(result).toHaveLength(1);
		const [url] = fetchMock.mock.calls[0] as [string];
		expect(url).toContain('/profile/embed-tokens');
	});

	it('createEmbedToken sends POST with name', async () => {
		apiKey.set('test-key');
		csrfToken.set('test-csrf');

		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: mockHeaders,
			json: async () => ({ token: 'le_newtoken123', embed_token: { id: 2, name: 'My Widget', token_prefix: 'le_newtoken1', scopes: 'embed:stats:read', allowed_origins: null, expires_at: null, last_used_at: null, created_at: '2024-01-01T00:00:00Z' } })
		} as unknown as Response);

		const result = await api.profile.createEmbedToken({ name: 'My Widget' });
		expect(result.token).toBe('le_newtoken123');
		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.method).toBe('POST');
		expect(init.body).toContain('My Widget');
	});

	it('createEmbedToken includes allowed_origins and expires_at when provided', async () => {
		apiKey.set('test-key');
		csrfToken.set('test-csrf');

		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: mockHeaders,
			json: async () => ({ token: 'le_newtoken456', embed_token: { id: 3, name: 'With Origins', token_prefix: 'le_newtoken4', scopes: 'embed:stats:read', allowed_origins: 'https://homarr.local', expires_at: null, last_used_at: null, created_at: '2024-01-01T00:00:00Z' } })
		} as unknown as Response);

		await api.profile.createEmbedToken({ name: 'With Origins', allowed_origins: 'https://homarr.local' });
		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.body).toContain('https://homarr.local');
	});

	it('updateEmbedToken sends PATCH with fields', async () => {
		apiKey.set('test-key');
		csrfToken.set('test-csrf');

		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: mockHeaders,
			json: async () => ({ id: 1, name: 'Renamed', token_prefix: 'le_abc', scopes: 'embed:stats:read', allowed_origins: null, expires_at: null, last_used_at: null, created_at: '2024-01-01T00:00:00Z' })
		} as unknown as Response);

		await api.profile.updateEmbedToken(1, { name: 'Renamed' });
		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.method).toBe('PATCH');
		expect(fetchMock.mock.calls[0][0]).toContain('/profile/embed-tokens/1');
	});

	it('rotateEmbedToken sends POST .../rotate', async () => {
		apiKey.set('test-key');
		csrfToken.set('test-csrf');

		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: mockHeaders,
			json: async () => ({ token: 'le_rotated', embed_token: { id: 4, name: 'Rotated', token_prefix: 'le_rotated', scopes: 'embed:stats:read', allowed_origins: null, expires_at: null, last_used_at: null, created_at: '2024-01-01T00:00:00Z' } })
		} as unknown as Response);

		await api.profile.rotateEmbedToken(1);
		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.method).toBe('POST');
		expect(fetchMock.mock.calls[0][0]).toContain('/profile/embed-tokens/1/rotate');
	});

	it('deleteEmbedToken sends DELETE', async () => {
		apiKey.set('test-key');
		csrfToken.set('test-csrf');

		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			headers: mockHeaders,
			json: async () => ({})
		} as unknown as Response);

		await api.profile.deleteEmbedToken(1);
		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.method).toBe('DELETE');
		expect(fetchMock.mock.calls[0][0]).toContain('/profile/embed-tokens/1');
	});
});

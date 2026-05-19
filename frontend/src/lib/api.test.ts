import { afterEach, describe, expect, it, vi } from 'vitest';
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

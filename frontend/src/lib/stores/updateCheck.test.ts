import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isNewer, checkForUpdate } from './updateCheck';

vi.mock('$lib/version', () => ({ version: 'v1.0.0', gitSha: 'abc1234' }));

const CHECK_URL = 'https://codebude.github.io/librislog/version.json';
const STORAGE_KEY = 'librislog_update_check';

function mockFetch(data: unknown, ok = true) {
	return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
		ok,
		json: async () => data,
	} as Response);
}

describe('isNewer', () => {
	it('returns true when latest is newer major', () => {
		expect(isNewer('v2.0.0', 'v1.0.0')).toBe(true);
	});

	it('returns true when latest is newer minor', () => {
		expect(isNewer('v1.2.0', 'v1.1.0')).toBe(true);
	});

	it('returns true when latest is newer patch', () => {
		expect(isNewer('v1.1.2', 'v1.1.1')).toBe(true);
	});

	it('returns false when versions are equal', () => {
		expect(isNewer('v1.1.1', 'v1.1.1')).toBe(false);
	});

	it('returns false when current is newer', () => {
		expect(isNewer('v1.0.0', 'v2.0.0')).toBe(false);
	});

	it('returns false for dev version as latest', () => {
		expect(isNewer('v0.0.0-dev', 'v1.0.0')).toBe(false);
	});

	it('handles pre-release tags', () => {
		expect(isNewer('v1.2.0-rc1', 'v1.1.0')).toBe(true);
	});

	it('treats final release as newer than its own pre-release', () => {
		expect(isNewer('v1.1.0', 'v1.1.0-rc1')).toBe(true);
	});

	it('detects newer pre-release over older release', () => {
		expect(isNewer('v1.2.0-rc1', 'v1.1.0')).toBe(true);
	});

	it('treats pre-release as older than next release', () => {
		expect(isNewer('v1.2.0', 'v1.1.0-rc1')).toBe(true);
	});

	it('handles version without v prefix', () => {
		expect(isNewer('2.0.0', '1.0.0')).toBe(true);
	});
});

describe('checkForUpdate', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.restoreAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('calls fetch once and returns update info', async () => {
		const fetchMock = mockFetch({ version: 'v2.0.0' });
		const result = await checkForUpdate();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(result).not.toBeNull();
	});

	it('returns UpdateInfo when a newer version is available', async () => {
		mockFetch({ version: 'v2.0.0', release_url: 'https://github.com/codebude/librislog/releases/tag/v2.0.0' });
		const result = await checkForUpdate();
		expect(result).toEqual({
			latestVersion: 'v2.0.0',
			releaseUrl: 'https://github.com/codebude/librislog/releases/tag/v2.0.0',
		});
	});

	it('falls back to generated release URL when release_url is missing', async () => {
		mockFetch({ version: 'v2.0.0' });
		const result = await checkForUpdate();
		expect(result?.releaseUrl).toBe('https://github.com/codebude/librislog/releases/tag/v2.0.0');
	});

	it('returns null when current version is already the latest', async () => {
		mockFetch({ version: 'v1.0.0' });
		const result = await checkForUpdate();
		expect(result).toBeNull();
	});

	it('returns null when current version is newer than the fetched one', async () => {
		mockFetch({ version: 'v0.9.0' });
		const result = await checkForUpdate();
		expect(result).toBeNull();
	});

	it('returns null on network error', async () => {
		vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'));
		const result = await checkForUpdate();
		expect(result).toBeNull();
	});

	it('returns null on non-ok response', async () => {
		mockFetch(null, false);
		const result = await checkForUpdate();
		expect(result).toBeNull();
	});

	it('returns null when response has no version field', async () => {
		mockFetch({});
		const result = await checkForUpdate();
		expect(result).toBeNull();
	});

	it('caches the result in localStorage', async () => {
		mockFetch({ version: 'v2.0.0' });
		await checkForUpdate();
		const cached = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
		expect(cached.data).toEqual({
			latestVersion: 'v2.0.0',
			releaseUrl: 'https://github.com/codebude/librislog/releases/tag/v2.0.0',
		});
		expect(typeof cached.timestamp).toBe('number');
	});

	it('reads from localStorage cache within TTL and does not fetch again', async () => {
		const cachedData = {
			timestamp: Date.now(),
			data: { latestVersion: 'v2.0.0', releaseUrl: 'https://github.com/codebude/librislog/releases/tag/v2.0.0' },
		};
		localStorage.setItem(STORAGE_KEY, JSON.stringify(cachedData));
		const fetchMock = mockFetch({ version: 'v3.0.0' });
		const result = await checkForUpdate();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(result).toEqual(cachedData.data);
	});

	it('fetches again when cache has expired', async () => {
		const cachedData = {
			timestamp: Date.now() - 61 * 60 * 1000,
			data: { latestVersion: 'v2.0.0', releaseUrl: '' },
		};
		localStorage.setItem(STORAGE_KEY, JSON.stringify(cachedData));
		const fetchMock = mockFetch({ version: 'v3.0.0' });
		const result = await checkForUpdate();
		expect(fetchMock).toHaveBeenCalledOnce();
		expect(result?.latestVersion).toBe('v3.0.0');
	});

	it('ignores malformed cache and fetches fresh', async () => {
		localStorage.setItem(STORAGE_KEY, 'not-json');
		const fetchMock = mockFetch({ version: 'v2.0.0' });
		const result = await checkForUpdate();
		expect(fetchMock).toHaveBeenCalledOnce();
		expect(result).not.toBeNull();
	});

	it('caches null result on failed fetch', async () => {
		vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('fail'));
		await checkForUpdate();
		const cached = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
		expect(cached.data).toBeNull();
	});

	it('skips fetch when cached null result is still valid', async () => {
		const cachedData = { timestamp: Date.now(), data: null };
		localStorage.setItem(STORAGE_KEY, JSON.stringify(cachedData));
		const fetchMock = mockFetch({ version: 'v2.0.0' });
		const result = await checkForUpdate();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(result).toBeNull();
	});
});

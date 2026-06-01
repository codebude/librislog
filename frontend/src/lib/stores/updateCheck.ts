import { version } from '$lib/version';

export interface UpdateInfo {
	latestVersion: string;
	releaseUrl: string;
}

const STORAGE_KEY = 'librislog_update_check';
const CACHE_TTL = 60 * 60 * 1000;
const CHECK_URL = 'https://codebude.github.io/librislog/version.json';

function parseVersion(v: string): { parts: number[]; isPreRelease: boolean } {
	const segments = v.replace(/^v/, '').split(/[.-]/);
	const nums = segments.map(Number);
	return {
		parts: nums.filter(n => !isNaN(n)),
		isPreRelease: nums.some(isNaN),
	};
}

export function isNewer(latest: string, current: string): boolean {
	const l = parseVersion(latest);
	const c = parseVersion(current);
	for (let i = 0; i < Math.max(l.parts.length, c.parts.length); i++) {
		const lv = l.parts[i] ?? 0;
		const cv = c.parts[i] ?? 0;
		if (lv > cv) return true;
		if (lv < cv) return false;
	}
	if (!l.isPreRelease && c.isPreRelease) return true;
	if (l.isPreRelease && !c.isPreRelease) return false;
	return false;
}

interface CachedData {
	timestamp: number;
	data: UpdateInfo | null;
}

export async function checkForUpdate(): Promise<UpdateInfo | null> {
	if (version === 'v0.0.0-dev') return null;

	const cached = localStorage.getItem(STORAGE_KEY);
	if (cached) {
		try {
			const parsed: CachedData = JSON.parse(cached);
			if (Date.now() - parsed.timestamp < CACHE_TTL) {
				return parsed.data;
			}
		} catch {
			/* stale cache */
		}
	}

	try {
		const res = await fetch(CHECK_URL);
		if (!res.ok) {
			localStorage.setItem(STORAGE_KEY, JSON.stringify({ timestamp: Date.now(), data: null }));
			return null;
		}
		const data: { version?: string; release_url?: string } = await res.json();
		if (!data.version || !isNewer(data.version, version)) {
			localStorage.setItem(STORAGE_KEY, JSON.stringify({ timestamp: Date.now(), data: null }));
			return null;
		}
		const info: UpdateInfo = {
			latestVersion: data.version,
			releaseUrl: data.release_url ?? `https://github.com/codebude/librislog/releases/tag/${data.version}`,
		};
		localStorage.setItem(STORAGE_KEY, JSON.stringify({ timestamp: Date.now(), data: info }));
		return info;
	} catch {
		localStorage.setItem(STORAGE_KEY, JSON.stringify({ timestamp: Date.now(), data: null }));
		return null;
	}
}

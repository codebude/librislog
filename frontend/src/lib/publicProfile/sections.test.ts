import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';
import en from '$lib/i18n/locales/en.json';
import type { PublicProfileSectionKey, PublicProfileStatisticsKey } from '$lib/types';
import {
	PUBLIC_PROFILE_SECTIONS,
	PUBLIC_PROFILE_STATISTICS,
	PUBLIC_PROFILE_STATISTICS_GROUPS,
	defaultPublicProfileVisibilityConfig
} from './sections';

// Compile-time guard: registries must stay assignable to the backend-driven unions.
const sectionKeys: PublicProfileSectionKey[] = PUBLIC_PROFILE_SECTIONS.map((s) => s.key);
const statisticKeys: PublicProfileStatisticsKey[] = PUBLIC_PROFILE_STATISTICS.map((s) => s.key);

const ALL_SECTIONS: PublicProfileSectionKey[] = [
	'username',
	'user_info',
	'currently_reading',
	'last_read',
	'reading_timeline',
	'full_library',
	'statistics'
];

const ALL_STATISTICS: PublicProfileStatisticsKey[] = [
	'total_books',
	'total_authors',
	'avg_books_per_month',
	'busiest_month',
	'avg_page_count',
	'most_popular_language',
	'language_distribution',
	'status_distribution',
	'acquisition_status_distribution',
	'medium_distribution',
	'page_buckets',
	'pages_read_per_month',
	'books_finished_per_month',
	'books_finished_per_year',
	'top_authors',
	'books_with_rating',
	'books_without_rating',
	'average_rating',
	'top_rated_books',
	'worst_rated_books'
];

function lookup(obj: unknown, path: string): unknown {
	return path.split('.').reduce<unknown>((acc, part) => (acc as Record<string, unknown>)?.[part], obj);
}

describe('public profile registries', () => {
	it('sections cover the full union with unique keys', () => {
		expect(new Set(sectionKeys).size).toBe(sectionKeys.length);
		expect([...sectionKeys].sort()).toEqual([...ALL_SECTIONS].sort());
	});

	it('statistics cover the full union with unique keys', () => {
		expect(new Set(statisticKeys).size).toBe(statisticKeys.length);
		expect([...statisticKeys].sort()).toEqual([...ALL_STATISTICS].sort());
	});

	it('every statistic belongs to a declared group', () => {
		const groups = [...new Set(PUBLIC_PROFILE_STATISTICS.map((s) => s.group))].sort();
		expect(groups).toEqual(['distribution', 'ratings', 'summary', 'trends']);
	});

	it('default visibility config derives from defaultOn flags', () => {
		const cfg = defaultPublicProfileVisibilityConfig();
		expect(cfg.sections).toEqual(PUBLIC_PROFILE_SECTIONS.filter((s) => s.defaultOn).map((s) => s.key));
		expect(cfg.statistics).toEqual(
			PUBLIC_PROFILE_STATISTICS.filter((s) => s.defaultOn).map((s) => s.key)
		);
	});

	it('every referenced i18n key exists in en.json', () => {
		const missing: string[] = [];
		for (const s of PUBLIC_PROFILE_SECTIONS) {
			for (const key of [s.i18nKey, s.tooltipKey]) {
				if (lookup(en, key) === undefined) missing.push(key);
			}
		}
		for (const g of PUBLIC_PROFILE_STATISTICS_GROUPS) {
			if (lookup(en, g.labelKey) === undefined) missing.push(g.labelKey);
		}
		for (const s of PUBLIC_PROFILE_STATISTICS) {
			if (lookup(en, s.i18nKey) === undefined) missing.push(s.i18nKey);
		}
		expect(missing).toEqual([]);
	});

	it('every i18n literal used by the public page renders a real string', () => {
		const src = readFileSync(
			resolve(process.cwd(), 'src/routes/p/[token]/+page.svelte'),
			'utf-8'
		);
		const literals = [
			...new Set(
				[...src.matchAll(/\$_\(\s*['"]([^'"]+)['"]/g)].map((m) => m[1])
			)
		];
		const missing = literals.filter((key) => lookup(en, key) === undefined);
		expect(missing).toEqual([]);
	});
});
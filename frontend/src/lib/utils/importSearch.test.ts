import { describe, it, expect } from 'vitest';
import {
	authorKey,
	candidateKey,
	groupCandidates,
	normalize,
	normalizeIsbn,
	titleAuthorKey
} from './importSearch';
import type { BookImportCandidate } from '$lib/types';

function makeCandidate(
	title: string,
	options: Partial<BookImportCandidate> = {}
): BookImportCandidate {
	return {
		title,
		subtitle: null,
		author: options.author ?? null,
		authors: options.authors ?? null,
		isbn: options.isbn ?? null,
		cover_url: options.cover_url ?? null,
		publisher: null,
		published_year: null,
		page_count: null,
		language: null,
		tags: null,
		blurb: null,
		source: options.source ?? 'open_library'
	};
}

describe('normalize', () => {
	it('trims and lowercases', () => {
		expect(normalize('  Dune ')).toBe('dune');
	});

	it('handles null/undefined', () => {
		expect(normalize(null)).toBe('');
		expect(normalize(undefined)).toBe('');
	});
});

describe('normalizeIsbn', () => {
	it('removes dashes and spaces', () => {
		expect(normalizeIsbn('978-0-441-01359-3')).toBe('9780441013593');
		expect(normalizeIsbn('978 0 441 01359 3')).toBe('9780441013593');
	});
});

describe('authorKey', () => {
	it('sorts and joins normalized authors', () => {
		expect(authorKey(['Frank Herbert', 'Brian Herbert'])).toBe('brian herbert|frank herbert');
	});

	it('handles null/empty', () => {
		expect(authorKey(null)).toBe('');
		expect(authorKey([])).toBe('');
	});
});

describe('candidateKey', () => {
	it('uses normalized ISBN when present', () => {
		const c = makeCandidate('Dune', { isbn: '978-0-441-01359-3' });
		expect(candidateKey(c)).toBe('isbn:9780441013593');
	});

	it('falls back to normalized title + sorted authors', () => {
		const c = makeCandidate('Dune', { authors: ['Frank Herbert'] });
		expect(candidateKey(c)).toBe('ta:dune|frank herbert');
	});

	it('is case-insensitive for title-only fallback', () => {
		const a = makeCandidate('DUNE', { authors: ['Frank Herbert'] });
		const b = makeCandidate('dune', { authors: ['frank herbert'] });
		expect(candidateKey(a)).toBe(candidateKey(b));
	});

	it('canonicalizes ISBN-10 and ISBN-13 to the same group key', () => {
		const isbn10 = '0441013597';
		const isbn13 = '9780441013593';
		const a = makeCandidate('Dune', { isbn: isbn10, source: 'open_library' });
		const b = makeCandidate('Dune', { isbn: isbn13, source: 'hardcover' });
		expect(candidateKey(a)).toBe(candidateKey(b));
	});

	it('never merges a 979-prefix ISBN-13 with an ISBN-10-derived key', () => {
		const isbn979 = '9791234567896';
		const isbn10 = '0441013597';
		const a = makeCandidate('A', { isbn: isbn979 });
		const b = makeCandidate('B', { isbn: isbn10 });
		expect(candidateKey(a)).not.toBe(candidateKey(b));
		expect(candidateKey(a)).toBe('isbn:9791234567896');
	});
});

describe('groupCandidates', () => {
	it('groups same-ISBN candidates into one group', () => {
		const ol = makeCandidate('Dune', { isbn: '9780441013593', source: 'open_library' });
		const hc = makeCandidate('Dune', { isbn: '9780441013593', source: 'hardcover' });
		const groups = groupCandidates([ol, hc]);

		expect(groups).toHaveLength(1);
		expect(groups[0].variants).toHaveLength(2);
		expect(groups[0].title).toBe('Dune');
	});

	it('keeps different-ISBN candidates as separate groups', () => {
		const a = makeCandidate('Dune', { isbn: '9780441013593' });
		const b = makeCandidate('Dune Messiah', { isbn: '9780441013609' });
		const groups = groupCandidates([a, b]);

		expect(groups).toHaveLength(2);
	});

	it('uses first available cover as group cover', () => {
		const a = makeCandidate('Dune', { isbn: '9780441013593', cover_url: null });
		const b = makeCandidate('Dune', { isbn: '9780441013593', cover_url: 'https://cover.jpg', source: 'hardcover' });
		const groups = groupCandidates([a, b]);

		expect(groups[0].coverUrl).toBe('https://cover.jpg');
	});

	it('preserves input order within a group', () => {
		const ol = makeCandidate('Dune', { isbn: '9780441013593', source: 'open_library' });
		const hc = makeCandidate('Dune', { isbn: '9780441013593', source: 'hardcover' });
		const gb = makeCandidate('Dune', { isbn: '9780441013593', source: 'google_books' });
		const groups = groupCandidates([ol, hc, gb]);

		expect(groups[0].variants.map((v) => v.source)).toEqual(['open_library', 'hardcover', 'google_books']);
	});
});

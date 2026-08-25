import { describe, expect, it } from 'vitest';
import { formatAuthors } from './authors';

describe('formatAuthors', () => {
	it('joins multiple authors with "; "', () => {
		expect(formatAuthors(['Terry Pratchett', 'Neil Gaiman'])).toBe('Terry Pratchett; Neil Gaiman');
	});

	it('returns the single author as-is', () => {
		expect(formatAuthors(['Frank Herbert'])).toBe('Frank Herbert');
	});

	it('returns the fallback for empty/null/undefined', () => {
		expect(formatAuthors([])).toBe('—');
		expect(formatAuthors(null)).toBe('—');
		expect(formatAuthors(undefined)).toBe('—');
	});

	it('supports a custom fallback', () => {
		expect(formatAuthors([], 'Unknown')).toBe('Unknown');
	});
});
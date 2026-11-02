import { describe, it, expect } from 'vitest';
import { chunk, findCaseVariants, mergeTagSuggestions } from './tagBatch';

describe('chunk', () => {
	it('splits into chunks of given size', () => {
		expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
	});
	it('returns single chunk when smaller', () => {
		expect(chunk([1, 2], 5)).toEqual([[1, 2]]);
	});
	it('returns empty for empty input', () => {
		expect(chunk([], 3)).toEqual([]);
	});
});

describe('findCaseVariants', () => {
	it('detects case-only differences', () => {
		const res = findCaseVariants(['sci-fi'], ['Sci-Fi']);
		expect(res).toEqual([{ name: 'sci-fi', existing: 'Sci-Fi' }]);
	});
	it('ignores exact matches', () => {
		expect(findCaseVariants(['Sci-Fi'], ['Sci-Fi'])).toEqual([]);
	});
	it('ignores unrelated names', () => {
		expect(findCaseVariants(['foo'], ['Bar'])).toEqual([]);
	});
	it('deduplicates reported variants', () => {
		const res = findCaseVariants(['a', 'A'], ['A']);
		expect(res.length).toBeLessThanOrEqual(1);
	});
});

describe('mergeTagSuggestions', () => {
	it('merges and dedupes case-insensitively', () => {
		expect(mergeTagSuggestions(['Foo', 'bar'], ['foo', 'baz'])).toEqual(['Foo', 'bar', 'baz']);
	});
});
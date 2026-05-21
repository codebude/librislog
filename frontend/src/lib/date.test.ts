import { describe, expect, it } from 'vitest';
import { toDateInputValue, fromDateInputValue, formatDate, formatDateTime, today } from './date';

describe('toDateInputValue', () => {
	it('converts UTC ISO to YYYY-MM-DD in UTC', () => {
		expect(toDateInputValue('2026-05-16T00:00:00.000Z', 'UTC')).toBe('2026-05-16');
	});

	it('converts UTC ISO to YYYY-MM-DD in Europe/Berlin', () => {
		expect(toDateInputValue('2026-05-16T00:00:00.000Z', 'Europe/Berlin')).toBe('2026-05-16');
	});

	it('converts UTC ISO to YYYY-MM-DD in America/New_York', () => {
		expect(toDateInputValue('2026-05-16T00:00:00.000Z', 'America/New_York')).toBe('2026-05-15');
	});

	it('returns empty string for null', () => {
		expect(toDateInputValue(null, 'UTC')).toBe('');
	});

	it('returns empty string for undefined', () => {
		expect(toDateInputValue(undefined, 'UTC')).toBe('');
	});

	it('returns empty string for invalid date', () => {
		expect(toDateInputValue('invalid', 'UTC')).toBe('');
	});
});

describe('fromDateInputValue', () => {
	it('converts YYYY-MM-DD to UTC ISO string for UTC timezone', () => {
		const result = fromDateInputValue('2026-05-16', 'UTC');
		expect(result).toBe('2026-05-16T00:00:00.000Z');
	});

	it('converts YYYY-MM-DD to UTC ISO string for Europe/Berlin', () => {
		const result = fromDateInputValue('2026-05-16', 'Europe/Berlin');
		expect(result).toBe('2026-05-15T22:00:00.000Z');
	});

	it('converts YYYY-MM-DD to UTC ISO string for America/New_York', () => {
		const result = fromDateInputValue('2026-05-16', 'America/New_York');
		expect(result).toBe('2026-05-16T04:00:00.000Z');
	});

	it('returns null for empty string', () => {
		expect(fromDateInputValue('', 'UTC')).toBeNull();
	});

	it('trims whitespace', () => {
		const result = fromDateInputValue(' 2026-05-16 ', 'UTC');
		expect(result).toBe('2026-05-16T00:00:00.000Z');
	});

	// Note: line 19 (isValid check) is unreachable because dayjs.tz() throws
	// for invalid input before isValid() can be called.
});

describe('formatDate', () => {
	it('formats date in UTC', () => {
		expect(formatDate('2026-05-16T00:00:00.000Z', 'UTC')).toBe('2026-05-16');
	});

	it('returns empty string for null', () => {
		expect(formatDate(null, 'UTC')).toBe('');
	});
});

describe('formatDateTime', () => {
	it('formats datetime in UTC', () => {
		expect(formatDateTime('2026-05-16T14:30:00.000Z', 'UTC')).toBe('2026-05-16 14:30');
	});

	it('formats datetime in Europe/Berlin', () => {
		expect(formatDateTime('2026-05-16T14:30:00.000Z', 'Europe/Berlin')).toBe('2026-05-16 16:30');
	});

	it('returns empty string for null', () => {
		expect(formatDateTime(null, 'UTC')).toBe('');
	});

	it('returns empty string for invalid date', () => {
		expect(formatDateTime('not-a-date', 'UTC')).toBe('');
	});
});

describe('today', () => {
	it('returns YYYY-MM-DD format', () => {
		const result = today('UTC');
		expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
	});
});

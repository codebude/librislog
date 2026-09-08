import { describe, expect, it } from 'vitest';
import {
	toDateInputValue,
	fromDateInputValue,
	formatDate,
	formatDateTime,
	toDateTimeInputValue,
	fromDateTimeInputValue,
	today
} from './date';

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

	it('returns null for invalid input', () => {
		expect(fromDateInputValue('garbage', 'UTC')).toBeNull();
	});
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

describe('toDateTimeInputValue', () => {
	it('converts UTC ISO to datetime-local value in UTC', () => {
		expect(toDateTimeInputValue('2026-05-16T14:30:00.000Z', 'UTC')).toBe('2026-05-16T14:30');
	});

	it('converts UTC ISO to datetime-local value in Europe/Berlin', () => {
		expect(toDateTimeInputValue('2026-05-16T14:30:00.000Z', 'Europe/Berlin')).toBe('2026-05-16T16:30');
	});

	it('converts UTC ISO to datetime-local value in America/New_York', () => {
		expect(toDateTimeInputValue('2026-05-16T04:30:00.000Z', 'America/New_York')).toBe('2026-05-16T00:30');
	});

	it('returns empty string for null', () => {
		expect(toDateTimeInputValue(null, 'UTC')).toBe('');
	});

	it('returns empty string for invalid date', () => {
		expect(toDateTimeInputValue('invalid', 'UTC')).toBe('');
	});
});

describe('fromDateTimeInputValue', () => {
	it('converts datetime-local value to UTC ISO for UTC timezone', () => {
		expect(fromDateTimeInputValue('2026-05-16T14:30', 'UTC')).toBe('2026-05-16T14:30:00.000Z');
	});

	it('converts datetime-local value to UTC ISO for Europe/Berlin', () => {
		expect(fromDateTimeInputValue('2026-05-16T14:30', 'Europe/Berlin')).toBe('2026-05-16T12:30:00.000Z');
	});

	it('converts datetime-local value to UTC ISO for America/New_York', () => {
		expect(fromDateTimeInputValue('2026-05-16T00:30', 'America/New_York')).toBe('2026-05-16T04:30:00.000Z');
	});

	it('returns null for empty string', () => {
		expect(fromDateTimeInputValue('', 'UTC')).toBeNull();
	});

	it('trims whitespace', () => {
		expect(fromDateTimeInputValue(' 2026-05-16T14:30 ', 'UTC')).toBe('2026-05-16T14:30:00.000Z');
	});

	it('returns null for invalid input', () => {
		expect(fromDateTimeInputValue('garbage', 'UTC')).toBeNull();
	});
});

describe('today', () => {
	it('returns YYYY-MM-DD format', () => {
		const result = today('UTC');
		expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
	});
});

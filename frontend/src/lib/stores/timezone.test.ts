import { describe, it, expect } from 'vitest';
import { setTimezone, getTimezone, detectTimezone, setQuoteServiceEnabled, isQuoteServiceEnabled } from '#lib/stores/timezone.js';

describe('timezone store', () => {
	it('getTimezone returns a string', () => {
		expect(typeof getTimezone()).toBe('string');
	});

	it('setTimezone updates timezone', () => {
		setTimezone('Europe/Berlin');
		expect(getTimezone()).toBe('Europe/Berlin');
		// Reset to default
		setTimezone('UTC');
	});

	it('detectTimezone returns a string', () => {
		expect(typeof detectTimezone()).toBe('string');
	});

	it('isQuoteServiceEnabled returns false by default', () => {
		expect(isQuoteServiceEnabled()).toBe(false);
	});

	it('setQuoteServiceEnabled updates the value', () => {
		setQuoteServiceEnabled(true);
		expect(isQuoteServiceEnabled()).toBe(true);
		setQuoteServiceEnabled(false);
		expect(isQuoteServiceEnabled()).toBe(false);
	});
});

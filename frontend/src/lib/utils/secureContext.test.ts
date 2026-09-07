import { describe, it, expect, afterEach } from 'vitest';
import { isSecureContext, SECURE_CONTEXT_DOCS_URL } from '$lib/utils/secureContext';

describe('isSecureContext', () => {
	const originalDescriptor = Object.getOwnPropertyDescriptor(window, 'isSecureContext');

	afterEach(() => {
		if (originalDescriptor) {
			Object.defineProperty(window, 'isSecureContext', originalDescriptor);
		}
	});

	it('returns true when window.isSecureContext is true', () => {
		Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
		expect(isSecureContext()).toBe(true);
	});

	it('returns false when window.isSecureContext is false', () => {
		Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false });
		expect(isSecureContext()).toBe(false);
	});
});

describe('SECURE_CONTEXT_DOCS_URL', () => {
	it('points to the library guide section on the docs site', () => {
		expect(SECURE_CONTEXT_DOCS_URL).toBe(
			'https://docs.librislog.app/guide/using-librislog/library.html#isbn-barcode-scan'
		);
	});
});
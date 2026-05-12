import { describe, expect, it } from 'vitest';
import { shouldShowActionToast } from './errors';

describe('shouldShowActionToast', () => {
	it('suppresses expected missing API key message', () => {
		expect(shouldShowActionToast('Missing API key')).toBe(false);
	});

	it('shows toast for other error messages', () => {
		expect(shouldShowActionToast('HTTP 500')).toBe(true);
		expect(shouldShowActionToast('Network error')).toBe(true);
	});
});

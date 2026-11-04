import { describe, it, expect } from 'vitest';

import { isActivePath } from './nav';

describe('isActivePath', () => {
	it('matches the exact route', () => {
		expect(isActivePath('/library', '/library')).toBe(true);
	});

	it('matches nested routes of the same section', () => {
		expect(isActivePath('/library/42', '/library')).toBe(true);
		expect(isActivePath('/library/42/edit', '/library')).toBe(true);
	});

	it('does not match other sections or prefix collisions', () => {
		expect(isActivePath('/dashboard', '/library')).toBe(false);
		expect(isActivePath('/libraryx', '/library')).toBe(false);
		expect(isActivePath('/', '/library')).toBe(false);
	});
});

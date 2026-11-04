import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect } from 'vitest';

import { CATPPUCCIN_THEMES } from '#lib/stores/theme.js';

const appCssPath = resolve(dirname(fileURLToPath(import.meta.url)), '../../app.css');
const appCss = readFileSync(appCssPath, 'utf8');

// The store accepts any name in CATPPUCCIN_THEMES, so a missing @plugin line
// would silently fall back to daisyUI's default theme instead of failing loudly.
describe('catppuccin theme registration', () => {
	it('registers a daisyUI plugin for every catppuccin flavor', () => {
		for (const flavor of CATPPUCCIN_THEMES) {
			expect(appCss).toContain(`@plugin "./lib/themes/catppuccin-${flavor}.ts";`);
		}
	});

	it('registers each flavor exactly once', () => {
		for (const flavor of CATPPUCCIN_THEMES) {
			const occurrences = appCss.split(`catppuccin-${flavor}.ts`).length - 1;
			expect(occurrences).toBe(1);
		}
	});
});

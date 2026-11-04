import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect } from 'vitest';

import { CATPPUCCIN_THEMES } from '#lib/stores/theme.js';

const appCssPath = resolve(dirname(fileURLToPath(import.meta.url)), '../../app.css');
const appCss = readFileSync(appCssPath, 'utf8');
// Comments can mention a plugin line without registering it.
const appCssWithoutComments = appCss.replace(/\/\*[\s\S]*?\*\//g, '');

// The store accepts any name in CATPPUCCIN_THEMES, so a missing @plugin line
// would silently fall back to daisyUI's default theme instead of failing loudly.
describe('catppuccin theme registration', () => {
	it('registers a daisyUI plugin for every catppuccin flavor', () => {
		for (const flavor of CATPPUCCIN_THEMES) {
			expect(appCssWithoutComments).toContain(`@plugin "./lib/themes/catppuccin-${flavor}.ts";`);
		}
	});

	it('registers each flavor exactly once', () => {
		for (const flavor of CATPPUCCIN_THEMES) {
			const occurrences = appCssWithoutComments.split(`catppuccin-${flavor}.ts`).length - 1;
			expect(occurrences).toBe(1);
		}
	});

	it('registers the flavors after the daisyui plugin so they are not overridden', () => {
		const daisyui = appCssWithoutComments.indexOf('@plugin "daisyui"');
		expect(daisyui).toBeGreaterThan(-1);
		for (const flavor of CATPPUCCIN_THEMES) {
			expect(appCssWithoutComments.indexOf(`catppuccin-${flavor}.ts`)).toBeGreaterThan(daisyui);
		}
	});
});

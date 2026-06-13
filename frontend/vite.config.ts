/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { svelteTesting } from '@testing-library/svelte/vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit(), svelteTesting()],
	server: {
		host: '0.0.0.0',
		proxy: {
			'^/api($|/)': 'http://localhost:8000',
			'^/embed($|/)': 'http://localhost:8000'
		}
	},
	test: {
		environment: 'happy-dom',
		globals: true,
		setupFiles: ['./src/lib/test/setup.ts'],
		include: ['src/**/*.{test,spec}.{js,ts}'],
		coverage: {
			provider: 'v8',
			reporter: ['text', 'json'],
			include: ['src/**/*.svelte', 'src/**/*.ts'],
			exclude: ['src/**/*.test.ts', 'src/**/*.spec.ts', 'src/lib/test/**', 'src/routes/**']
		}
	}
});

import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: './e2e/specs',
	fullyParallel: false,
	retries: 1,
	workers: 1,
	globalSetup: './e2e/config/global-setup.ts',
	globalTeardown: './e2e/config/global-teardown.ts',
	reporter: [
		['html', { outputFolder: 'playwright-report' }],
		['list'],
	],
	use: {
		baseURL: 'http://localhost:8003',
		headless: true,
		viewport: { width: 1280, height: 800 },
		ignoreHTTPSErrors: true,
		screenshot: 'only-on-failure',
		trace: 'retain-on-failure',
	},
	timeout: 60_000,
	expect: {
		timeout: 15_000,
	},
});

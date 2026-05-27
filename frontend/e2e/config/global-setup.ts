import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import type { FullConfig } from '@playwright/test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const COMPOSE_FILE = 'docker-compose.e2e.yml';
const BACKEND_URL = 'http://localhost:8002/api/health';
const FRONTEND_URL = 'http://localhost:8003';

async function isHealthy(url: string): Promise<boolean> {
	return fetch(url)
		.then(r => r.ok)
		.catch(() => false);
}

async function waitForHealthy(url: string, label: string, timeoutMs = 90_000): Promise<void> {
	const start = Date.now();
	while (Date.now() - start < timeoutMs) {
		if (await isHealthy(url)) {
			console.log(`  ✓ ${label} is healthy`);
			return;
		}
		await new Promise(r => setTimeout(r, 2000));
	}
	throw new Error(`${label} did not become healthy within ${timeoutMs / 1000}s`);
}

async function globalSetup(_config: FullConfig) {
	if (await isHealthy(BACKEND_URL) && await isHealthy(FRONTEND_URL)) {
		console.log('✓ E2E Docker stack is already running');
		return;
	}

	console.log('Cleaning previous test data...');
	execSync(`rm -rf ${path.join(PROJECT_ROOT, 'data-e2e')}`, { stdio: 'inherit' });

	console.log('Starting E2E Docker stack...');
	execSync(
		`docker compose -f ${COMPOSE_FILE} up -d --build`,
		{ cwd: PROJECT_ROOT, stdio: 'inherit', timeout: 300_000 }
	);

	await waitForHealthy(BACKEND_URL, 'Backend');
	await waitForHealthy(FRONTEND_URL, 'Frontend');

	console.log('✓ E2E Docker stack is ready — starting tests');
}

export default globalSetup;

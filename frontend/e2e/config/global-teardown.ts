import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import type { FullConfig } from '@playwright/test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const COMPOSE_FILE = 'docker-compose.e2e.yml';

async function globalTeardown(_config: FullConfig) {
	console.log('Stopping E2E Docker stack...');
	try {
		execSync(
			`docker compose -f ${COMPOSE_FILE} down`,
			{ cwd: PROJECT_ROOT, stdio: 'inherit', timeout: 60_000 }
		);
		console.log('✓ E2E Docker stack stopped');
	} catch {
		console.log('⚠  Failed to stop E2E Docker stack (may already be stopped)');
	}
}

export default globalTeardown;

import type { FullConfig } from '@playwright/test';

const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://backend:8000/api/health';

async function globalSetup(_config: FullConfig) {
	const healthy = await fetch(BACKEND_URL)
		.then(r => r.ok)
		.catch(() => false);

	if (!healthy) {
		throw new Error(
			`Backend not reachable at ${BACKEND_URL}.\n` +
			'Ensure the E2E Docker stack is running:\n' +
			'  docker compose -f docker-compose.e2e.yml up --build'
		);
	}

	console.log('✓ Backend is healthy');
}

export default globalSetup;

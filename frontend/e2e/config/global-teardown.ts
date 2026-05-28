async function globalTeardown() {
	// Cleanup is handled by docker compose --abort-on-container-exit
	console.log('✓ E2E tests finished');
}

export default globalTeardown;

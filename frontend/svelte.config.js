import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({ fallback: '200.html' }),
		version: {
			name: process.env.APP_VERSION || 'v0.0.0-dev'
		}
	}
};

export default config;

<script lang="ts">
	import { _ } from '$lib/i18n';
	import Logo from '$lib/components/Logo.svelte';
	import { version, gitSha } from '$lib/version';
	import pkg from '../../../package.json';

	const frontendDeps = Object.entries(pkg.dependencies).sort((a, b) => a[0].localeCompare(b[0]));
	const devDeps = Object.entries(pkg.devDependencies).sort((a, b) => a[0].localeCompare(b[0]));

	const additionalDeps: Array<{ name: string; url: string }> = [
		{ name: '@lucide/svelte', url: 'https://lucide.dev/' },
		{ name: '@fontsource/inter', url: 'https://fontsource.org/fonts/inter' },
		{ name: 'Chart.js', url: 'https://www.chartjs.org/' },
		{ name: 'svelte-chartjs', url: 'https://github.com/SauravKanchan/svelte-chartjs' },
		{ name: 'chartjs-plugin-zoom', url: 'https://github.com/chartjs/chartjs-plugin-zoom' },
		{ name: 'chartjs-chart-matrix', url: 'https://github.com/kurkle/chartjs-chart-matrix' },
		{ name: 'DaisyUI', url: 'https://daisyui.com/' },
		{ name: 'Hammer.js', url: 'https://hammerjs.github.io/' },
		{ name: 'html5-qrcode', url: 'https://github.com/mebjas/html5-qrcode' },
		{ name: 'animal-avatar-generator', url: 'https://github.com/roma-lukashik/animal-avatar-generator' },
		{ name: 'dayjs', url: 'https://day.js.org/' },
		{ name: 'svelte-i18n', url: 'https://github.com/kaisermann/svelte-i18n' },
		{ name: 'VitePress', url: 'https://vitepress.dev/' },
		{ name: 'viewerjs', url: 'https://github.com/fengyuanchen/viewerjs' },
	];


	const backendDeps: Array<{ name: string; url: string }> = [
		{ name: 'FastAPI', url: 'https://fastapi.tiangolo.com/' },
		{ name: 'SQLModel', url: 'https://sqlmodel.tiangolo.com/' },
		{ name: 'SQLAlchemy', url: 'https://www.sqlalchemy.org/' },
		{ name: 'Alembic', url: 'https://alembic.sqlalchemy.org/' },
		{ name: 'Pydantic', url: 'https://docs.pydantic.dev/' },
		{ name: 'Authlib', url: 'https://authlib.org/' },
		{ name: 'httpx', url: 'https://www.python-httpx.org/' },
		{ name: 'Uvicorn', url: 'https://www.uvicorn.org/' },
		{ name: 'Scrapling', url: 'https://github.com/scrapling/Scrapling' },
		{ name: 'curl-cffi', url: 'https://github.com/yifeikong/curl_cffi' },
		{ name: 'Playwright', url: 'https://playwright.dev/python/' },
		{ name: 'python-multipart', url: 'https://github.com/andrew-d/python-multipart' },
		{ name: 'cachetools', url: 'https://github.com/tkem/cachetools' },
		{ name: 'cryptography', url: 'https://cryptography.io/' },
		{ name: 'passlib', url: 'https://passlib.readthedocs.io/' },
		{ name: 'pycountry', url: 'https://github.com/flyingcircusio/pycountry' },
		{ name: 'pydantic-settings', url: 'https://docs.pydantic.dev/latest/concepts/pydantic_settings/' },
		{ name: 'itsdangerous', url: 'https://itsdangerous.palletsprojects.com/' },
		{ name: 'browserforge', url: 'https://github.com/ultrafunkamsterdam/browserforge' },
		{ name: 'RestrictedPython', url: 'https://github.com/zopefoundation/RestrictedPython' },
		{ name: 'Typer', url: 'https://typer.tiangolo.com/' },
		{ name: 'Rich', url: 'https://rich.readthedocs.io/' },
	];

	const displayVersion = $derived(
		version +
			(gitSha && gitSha !== 'unknown' && !version.includes(gitSha.slice(0, 7))
				? ` (${gitSha.slice(0, 7)})`
				: '')
	);
</script>

<div class="max-w-3xl mx-auto flex flex-col gap-6">
	<h1 class="text-2xl font-bold">{$_('about.title')}</h1>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-4">
			<div class="flex items-center gap-4">
				<Logo class="w-14 h-14" />
				<div>
					<h2 class="text-xl font-bold">LibrisLog</h2>
					<p class="text-sm text-base-content/60">{displayVersion}</p>
				</div>
			</div>
			<p class="text-sm text-base-content/70 leading-relaxed">
				{$_('about.description')}
			</p>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('about.author')}</h2>
			<div class="flex items-center gap-3">
				<div class="w-12 h-12 rounded-full bg-primary text-primary-content text-lg grid place-items-center font-bold">
					RH
				</div>
				<div>
					<p class="font-medium">Raffael Herrmann</p>
					<a
						href="https://github.com/codebude"
						target="_blank"
						rel="noopener noreferrer"
						class="link link-primary text-sm"
					>github.com/codebude</a>
				</div>
			</div>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-4">
			<h2 class="text-lg font-semibold">{$_('about.technologies')}</h2>

			<div>
				<h3 class="text-sm font-semibold text-base-content/70 uppercase tracking-wider mb-2">{$_('about.frontend')}</h3>
				<div class="flex flex-wrap gap-1.5">
					{#each frontendDeps as [name, ver]}
						<a
							href="https://www.npmjs.com/package/{name}"
							target="_blank"
							rel="noopener noreferrer"
							class="badge badge-outline badge-sm hover:badge-primary transition-colors"
						>{name}</a>
					{/each}
					{#each additionalDeps as dep}
						<a
							href={dep.url}
							target="_blank"
							rel="noopener noreferrer"
							class="badge badge-outline badge-sm hover:badge-primary transition-colors"
						>{dep.name}</a>
					{/each}
				</div>
			</div>

			<div>
				<h3 class="text-sm font-semibold text-base-content/70 uppercase tracking-wider mb-2">{$_('about.backend')}</h3>
				<div class="flex flex-wrap gap-1.5">
					{#each backendDeps as dep}
						<a
							href={dep.url}
							target="_blank"
							rel="noopener noreferrer"
							class="badge badge-outline badge-sm hover:badge-primary transition-colors"
						>{dep.name}</a>
					{/each}
				</div>
			</div>

			<div>
				<h3 class="text-sm font-semibold text-base-content/70 uppercase tracking-wider mb-2">{$_('about.devTools')}</h3>
				<div class="flex flex-wrap gap-1.5">
					{#each devDeps as [name, ver]}
						<a
							href="https://www.npmjs.com/package/{name}"
							target="_blank"
							rel="noopener noreferrer"
							class="badge badge-outline badge-sm hover:badge-primary transition-colors"
						>{name}</a>
					{/each}
				</div>
			</div>
		</div>
	</div>

	<div class="card bg-base-100 border border-base-200 shadow-sm">
		<div class="card-body gap-3">
			<h2 class="text-lg font-semibold">{$_('about.thankYou')}</h2>
			<p class="text-sm text-base-content/70 leading-relaxed">
				{$_('about.thankYouText')}
			</p>
		</div>
	</div>
</div>

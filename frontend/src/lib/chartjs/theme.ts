const colorCache = new Map<string, string>();

const VAR_MAP: Record<string, string> = {
	primary: '--color-primary',
	secondary: '--color-secondary',
	accent: '--color-accent',
	info: '--color-info',
	success: '--color-success',
	warning: '--color-warning',
	error: '--color-error',
	'base-100': '--color-base-100',
	'base-200': '--color-base-200',
	'base-300': '--color-base-300',
	'base-content': '--color-base-content',
};

export function getCssColor(varName: string, fallback = '#999'): string {
	if (typeof window === 'undefined') return fallback;
	const cached = colorCache.get(varName);
	if (cached) return cached;

	const el = document.createElement('div');
	el.style.color = `var(${varName})`;
	el.style.position = 'absolute';
	el.style.visibility = 'hidden';
	el.style.pointerEvents = 'none';
	document.body.appendChild(el);
	try {
		const computed = getComputedStyle(el).color;
		const result = computed || fallback;
		colorCache.set(varName, result);
		return result;
	} finally {
		document.body.removeChild(el);
	}
}

export function invalidateColorCache(): void {
	colorCache.clear();
}

export function resolveDaisyColor(name: string): string {
	const varName = VAR_MAP[name];
	if (!varName) {
		console.warn(`resolveDaisyColor: unknown color "${name}", falling back to primary`);
		return 'var(--color-primary)';
	}
	return `var(${varName})`;
}

export function getDaisyColorRgb(name: string): string {
	const varName = VAR_MAP[name];
	if (!varName) {
		return getCssColor('--color-primary', 'rgb(0, 0, 0)');
	}
	return getCssColor(varName, 'rgb(0, 0, 0)');
}

function oklchToRgb(l: number, c: number, h: number): [number, number, number] {
	const hr = (h * Math.PI) / 180;
	const a = c * Math.cos(hr);
	const b = c * Math.sin(hr);

	const lm = l + 0.3963377774 * a + 0.2158037573 * b;
	const mm = l - 0.1055613458 * a - 0.0638541728 * b;
	const sm = l - 0.0894841775 * a - 1.291485548 * b;

	const l3 = lm * lm * lm;
	const m3 = mm * mm * mm;
	const s3 = sm * sm * sm;

	let r = 4.0767416621 * l3 - 3.3077115391 * m3 + 0.2309699203 * s3;
	let g = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3;
	let bl = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.707614701 * s3;

	const toSrgb = (v: number): number => {
		v = Math.max(0, Math.min(1, v));
		return v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055;
	};

	return [
		Math.round(toSrgb(r) * 255),
		Math.round(toSrgb(g) * 255),
		Math.round(toSrgb(bl) * 255),
	];
}

function parseColor(c: string): [number, number, number] {
	if (c.startsWith('#')) {
		const hex = c.replace('#', '');
		if (hex.length === 3) {
			return [
				parseInt(hex[0] + hex[0], 16),
				parseInt(hex[1] + hex[1], 16),
				parseInt(hex[2] + hex[2], 16),
			];
		}
		return [
			parseInt(hex.slice(0, 2), 16),
			parseInt(hex.slice(2, 4), 16),
			parseInt(hex.slice(4, 6), 16),
		];
	}

	const oklch = c.match(/oklch\(\s*([\d.]+)%?\s+([\d.]+)\s+([\d.]+)/);
	if (oklch) {
		const l = parseFloat(oklch[1]);
		const c = parseFloat(oklch[2]);
		const h = parseFloat(oklch[3]);
		return oklchToRgb(l, c, h);
	}

	const rgb = c.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
	if (rgb) return [+rgb[1], +rgb[2], +rgb[3]];

	return [0, 0, 0];
}

export function mixDaisyColors(
	fromVar: string,
	toVar: string,
	t: number
): string {
	if (typeof window === 'undefined') return 'transparent';
	t = Math.max(0, Math.min(1, t));

	const from = getCssColor(fromVar, '#e5e7eb');
	const to = getCssColor(toVar, '#3b82f6');

	const [r1, g1, b1] = parseColor(from);
	const [r2, g2, b2] = parseColor(to);

	const r = Math.round(r1 + (r2 - r1) * t);
	const g = Math.round(g1 + (g2 - g1) * t);
	const b = Math.round(b1 + (b2 - b1) * t);

	return `rgb(${r}, ${g}, ${b})`;
}

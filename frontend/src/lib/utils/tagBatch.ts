export function chunk<T>(items: T[], size: number): T[][] {
	if (size <= 0) throw new Error('chunk size must be positive');
	const out: T[][] = [];
	for (let i = 0; i < items.length; i += size) {
		out.push(items.slice(i, i + size));
	}
	return out;
}

export interface CaseVariant {
	name: string;
	existing: string;
}

export function findCaseVariants(names: string[], existingNames: string[]): CaseVariant[] {
	const seen = new Map(existingNames.map((n) => [n.toLowerCase(), n]));
	const result: CaseVariant[] = [];
	const reported = new Set<string>();
	for (const name of names) {
		const key = name.toLowerCase();
		const existing = seen.get(key);
		if (existing && existing !== name && !reported.has(key)) {
			result.push({ name, existing });
			reported.add(key);
		}
	}
	return result;
}

export function mergeTagSuggestions(primary: string[], secondary: string[]): string[] {
	const out: string[] = [];
	const seen = new Set<string>();
	for (const name of [...primary, ...secondary]) {
		const key = name.toLowerCase();
		if (seen.has(key)) continue;
		seen.add(key);
		out.push(name);
	}
	return out;
}
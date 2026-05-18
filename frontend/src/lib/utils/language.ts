export function formatLanguageCode(code: string | null | undefined, locale: string): string {
	if (!code) return '-';
	const normalized = code.trim().toLowerCase();
	if (!normalized) return '-';

	try {
		const displayNames = new Intl.DisplayNames([locale], { type: 'language' });
		return displayNames.of(normalized) ?? code.toUpperCase();
	} catch {
		return code.toUpperCase();
	}
}

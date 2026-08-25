export function formatAuthors(
	authors: string[] | null | undefined,
	fallback: string | null | undefined = '—'
): string {
	if (!authors || authors.length === 0) return fallback || '—';
	return authors.join('; ');
}
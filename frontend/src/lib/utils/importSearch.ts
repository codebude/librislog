import type { BookImportCandidate, BookImportCandidateGroup } from '$lib/types';

export function normalize(value: string | null | undefined): string {
	return (value ?? '').trim().toLowerCase();
}

export function normalizeIsbn(value: string | null | undefined): string {
	return normalize(value).replaceAll('-', '').replaceAll(' ', '');
}

function isbn10ToIsbn13(isbn10: string): string {
	if (isbn10.length !== 10) return isbn10;
	const head = isbn10.slice(0, 9);
	if (!/^\d{9}$/.test(head)) return isbn10;
	const tail = isbn10[9];
	if (!/[\dXx]/.test(tail)) return isbn10;
	const digits = `978${head}`;
	let sum = 0;
	for (let i = 0; i < digits.length; i++) {
		sum += parseInt(digits[i], 10) * (i % 2 === 0 ? 1 : 3);
	}
	const check = (10 - (sum % 10)) % 10;
	return `${digits}${check}`;
}

export function canonicalIsbn(isbn: string): string {
	const clean = normalizeIsbn(isbn);
	if (clean.length === 10) {
		return isbn10ToIsbn13(clean);
	}
	return clean;
}

export function authorKey(authors: string[] | null | undefined): string {
	return (authors ?? [])
		.map((a) => normalize(a))
		.filter(Boolean)
		.sort()
		.join('|');
}

export function titleAuthorKey(title: string | null | undefined, authors: string[]): string {
	return `${normalize(title)}|${authorKey(authors)}`;
}

export function candidateKey(candidate: BookImportCandidate): string {
	const isbn = normalizeIsbn(candidate.isbn);
	if (isbn) return `isbn:${canonicalIsbn(isbn)}`;
	return `ta:${normalize(candidate.title)}|${authorKey(candidate.authors)}`;
}

export function groupCandidates(candidates: BookImportCandidate[]): BookImportCandidateGroup[] {
	const map = new Map<string, BookImportCandidate[]>();
	for (const candidate of candidates) {
		const key = candidateKey(candidate);
		const list = map.get(key) ?? [];
		list.push(candidate);
		map.set(key, list);
	}

	const groups: BookImportCandidateGroup[] = [];
	for (const [key, variants] of map) {
		const representative = variants[0];
		const coverUrl = variants.find((v) => v.cover_url)?.cover_url ?? null;
		groups.push({
			key,
			title: representative.title,
			authors: representative.authors,
			coverUrl,
			variants
		});
	}
	return groups;
}

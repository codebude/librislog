export const SECURE_CONTEXT_DOCS_URL =
	'https://docs.librislog.app/guide/using-librislog/library.html#isbn-barcode-scan';

export function isSecureContext(): boolean {
	return typeof window !== 'undefined' && window.isSecureContext === true;
}
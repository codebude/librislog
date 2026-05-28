const BACKEND_ERROR_MAP: Record<string, string> = {
	'Email already registered': 'error.emailAlreadyRegistered',
	'User not found': 'error.userNotFound',
	'Cannot change your own admin role': 'error.cannotChangeOwnRole',
	'This ISBN is already used by another book.': 'error.isbnAlreadyExists',
	'Date cannot be in the future.': 'error.dateInFuture',
	'Start date cannot be after finish date.': 'error.dateStartedAfterFinished',
	'A finished book must have an end date. Change the status if you want to remove the finish date.': 'error.dateFinishedRequiredForRead',
	'Language must be a 2-letter ISO code (for example: EN, DE, FR).': 'error.invalidLanguageCode',
	'Select at least one dataset to export.': 'error.exportNoDatasets',
	'Unsupported upload content type. Use CSV or JSON files.': 'error.importUnsupportedContentType',
	'A mapping with this name already exists.': 'error.importMappingNameConflict',
	'Import mapping not found.': 'error.importMappingNotFound',
	'Confirmation phrase does not match.': 'error.invalidConfirmationPhrase',
	'Batch update failed due to a database error': 'error.batchUpdateFailed',
	'Cannot delete the last administrator account.': 'error.cannotDeleteLastAdmin',
	'You cannot delete your own account here. Use Profile > Danger Zone.': 'error.cannotDeleteOwnAccountHere',
};

const BACKEND_ERROR_REGEX: [RegExp, string, string[]][] = [
	[/^At most (\d+) books can be updated at once$/, 'error.tooManyBooksSelected', ['max']],
];

export function localizeBackendError(err: unknown): { key: string; values?: Record<string, unknown> } {
	if (err instanceof Error) {
		if (err.message.startsWith('error.')) {
			return { key: err.message };
		}
		const exactKey = BACKEND_ERROR_MAP[err.message];
		if (exactKey) {
			return { key: exactKey };
		}
		for (const [pattern, key, names] of BACKEND_ERROR_REGEX) {
			const match = err.message.match(pattern);
			if (match) {
				const values: Record<string, unknown> = {};
				for (let i = 0; i < names.length; i++) {
					values[names[i]] = match[i + 1];
				}
				return { key, values };
			}
		}
		return { key: err.message };
	}
	return { key: 'Unknown error' };
}

export function localizeError(err: unknown, translate: (key: string, options?: { values?: Record<string, unknown> }) => string, fallback: string): string {
	const { key, values } = localizeBackendError(err);
	if (key.startsWith('error.')) {
		return translate(key, values ? { values } : undefined);
	}
	if (key !== 'Unknown error') {
		return key;
	}
	return fallback;
}

export function shouldShowActionToast(message: string): boolean {
	return message !== 'Missing API key' && message !== 'Not authenticated';
}

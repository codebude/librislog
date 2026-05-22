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
	'Cannot delete the last administrator account.': 'error.cannotDeleteLastAdmin',
	'You cannot delete your own account here. Use Profile > Danger Zone.': 'error.cannotDeleteOwnAccountHere',
};

export function localizeBackendError(err: unknown): string {
	if (err instanceof Error) {
		if (err.message.startsWith('error.')) {
			return err.message;
		}
		const mappedKey = BACKEND_ERROR_MAP[err.message];
		if (mappedKey) {
			return mappedKey;
		}
		return err.message;
	}
	return 'Unknown error';
}

export function localizeError(err: unknown, translate: (key: string) => string, fallback: string): string {
	const localized = localizeBackendError(err);
	if (localized.startsWith('error.')) {
		return translate(localized);
	}
	if (localized !== 'Unknown error') {
		return localized;
	}
	return fallback;
}

export function shouldShowActionToast(message: string): boolean {
	return message !== 'Missing API key' && message !== 'Not authenticated';
}

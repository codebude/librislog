import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import ImportSearch from './ImportSearch.svelte';
import { api } from '$lib/api';
import type { BookImportCandidate, SearchStage } from '$lib/types';

const mockSearchStream = vi.fn();
const mockImportBook = vi.fn();
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		import: {
			searchStream: (...args: unknown[]) => mockSearchStream(...args),
			importBook: (...args: unknown[]) => mockImportBook(...args)
		},
		books: {
			list: vi.fn(async () => ({ books: [], total: 0 }))
		}
	}
}));

vi.mock('$lib/toasts', () => ({
	toasts: {
		add: (...args: unknown[]) => mockToastsAdd(...args),
		remove: vi.fn(),
		subscribe: vi.fn()
	}
}));

function candidate(
	id: number,
	title: string,
	options: Partial<BookImportCandidate> = {}
): BookImportCandidate {
	return {
		title,
		subtitle: null,
		author: options.author ?? null,
		authors: options.authors ?? [],
		isbn: options.isbn ?? `978000000000${id}`,
		cover_url: options.cover_url ?? null,
		publisher: null,
		published_year: options.published_year ?? null,
		page_count: options.page_count ?? null,
		language: options.language ?? null,
		tags: null,
		blurb: null,
		source: options.source ?? 'open_library'
	};
}

function stageComplete(results: BookImportCandidate[]): SearchStage {
	return { stage: 'complete', results };
}

type StreamArgs = [unknown, unknown, unknown, AbortSignal?];

function onAbort(signal: AbortSignal | undefined, handler: () => void) {
	if (!signal) return;
	if (signal.aborted) {
		handler();
		return;
	}
	signal.addEventListener('abort', handler, { once: true });
}

function abortError(): Error {
	const err = new Error('The user aborted a request.');
	err.name = 'AbortError';
	return err;
}

function makeStream({ delay = 10_000 } = {}) {
	return async function* (_q: unknown, _t: unknown, _m: unknown, signal?: AbortSignal) {
		await new Promise<void>((resolve, reject) => {
			onAbort(signal, () => reject(abortError()));
			setTimeout(resolve, delay);
		});
		yield stageComplete([candidate(1, 'Book 0')]);
	};
}

function makeStreamWithResults(results: BookImportCandidate[]) {
	return async function* (_q: unknown, _t: unknown, _m: unknown, signal?: AbortSignal) {
		yield stageComplete(results);
		await new Promise<void>((_resolve, reject) => {
			onAbort(signal, () => reject(abortError()));
		});
	};
}

function makeStreamFinishing(results: BookImportCandidate[]) {
	return async function* (_q: unknown, _t: unknown, _m: unknown, _signal?: AbortSignal) {
		yield stageComplete(results);
	};
}

async function typeQueryAndSearch() {
	const input = screen.getByPlaceholderText(/Search by title or author/);
	await fireEvent.input(input, { target: { value: 'dune' } });
	await fireEvent.click(screen.getByRole('button', { name: 'Search' }));
}

describe('ImportSearch', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.books.list).mockResolvedValue({ books: [], total: 0 });
	});

	afterEach(() => {
		cleanup();
	});

	describe('cancelable search', () => {
		it('turns the Search button into Cancel while searching', async () => {
			mockSearchStream.mockImplementation(makeStream());

			render(ImportSearch, {});
			await typeQueryAndSearch();

			expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
		});

		it('aborts the active request and resets to Search when Cancel is clicked', async () => {
			let capturedSignal: AbortSignal | undefined;
			mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
				capturedSignal = args[3];
				yield* makeStream()(...args);
			});

			render(ImportSearch, {});
			await typeQueryAndSearch();

			expect(capturedSignal).toBeDefined();
			expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();

			await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

			await waitFor(() => {
				expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
				expect(capturedSignal?.aborted).toBe(true);
			});
		});

		it('discards partial results when Cancel is clicked', async () => {
			const dune = candidate(1, 'Dune', { authors: ['Frank Herbert'], isbn: '9780441013593' });
			const duneMessiah = candidate(2, 'Dune Messiah', {
				authors: ['Frank Herbert'],
				isbn: '9780441013609'
			});
			mockSearchStream.mockImplementation(makeStreamWithResults([dune, duneMessiah]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			expect(screen.getByText('Dune Messiah')).toBeInTheDocument();

			await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

			await waitFor(() => {
				expect(screen.queryByText('Dune')).not.toBeInTheDocument();
				expect(screen.queryByText('Dune Messiah')).not.toBeInTheDocument();
				expect(screen.getByText('No results yet')).toBeInTheDocument();
			});
		});

		it('does not show an error toast for AbortError', async () => {
			mockSearchStream.mockImplementation(makeStream());

			render(ImportSearch, {});
			await typeQueryAndSearch();
			await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

			await waitFor(() => {
				expect(mockToastsAdd).not.toHaveBeenCalled();
			});
		});

		it('starts a fresh search with a new signal after cancelling', async () => {
			const signals: AbortSignal[] = [];
			mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
				const signal = args[3];
				if (signal) signals.push(signal);
				yield* makeStream()(...args);
			});

			render(ImportSearch, {});
			await typeQueryAndSearch();
			await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
			await waitFor(() => {
				expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
			});

			await typeQueryAndSearch();
			expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
			expect(signals).toHaveLength(2);
			expect(signals[0]).not.toBe(signals[1]);
		});

		it('aborts pending search on unmount', async () => {
			const abortSpy = vi.fn();
			let capturedSignal: AbortSignal | undefined;
			mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
				capturedSignal = args[3];
				onAbort(capturedSignal, abortSpy);
				yield* makeStream()(...args);
			});

			const { unmount } = render(ImportSearch, {});
			await typeQueryAndSearch();

			expect(capturedSignal).toBeDefined();
			unmount();

			expect(abortSpy).toHaveBeenCalledTimes(1);
		});
	});

	describe('grouped results', () => {
		it('groups same-ISBN candidates and shows a count badge', async () => {
			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const hc = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover',
				page_count: 464
			});
			mockSearchStream.mockImplementation(makeStreamFinishing([ol, hc]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			expect(screen.getByText('2 results')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Show editions' })).toBeInTheDocument();
		});

		it('expands a group to reveal all variants', async () => {
			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const hc = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover'
			});
			mockSearchStream.mockImplementation(makeStreamFinishing([ol, hc]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			await fireEvent.click(screen.getByRole('button', { name: 'Show editions' }));

			await waitFor(() => {
				expect(screen.getByText('hardcover')).toBeInTheDocument();
				expect(screen.getAllByText('open_library').length).toBeGreaterThanOrEqual(1);
			});
		});

		it('imports the selected variant when Add is clicked', async () => {
			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const hc = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover'
			});
			mockImportBook.mockResolvedValue({ id: 1, title: 'Dune' });
			mockSearchStream.mockImplementation(makeStreamFinishing([ol, hc]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});

			// Select the hardcover variant and then import.
			await fireEvent.click(screen.getByRole('button', { name: 'Show editions' }));
			await waitFor(() => {
				expect(screen.getByText('hardcover')).toBeInTheDocument();
			});
			const variantButtons = screen.getAllByRole('button').filter((b) => b.textContent?.includes('hardcover'));
			await fireEvent.click(variantButtons[0]);

			const acquisitionSelect = screen.getByRole('combobox', { name: /Possession/i });
			await fireEvent.change(acquisitionSelect, { target: { value: 'owned' } });

			await fireEvent.click(screen.getByRole('button', { name: 'Add' }));

			await waitFor(() => {
				expect(mockImportBook).toHaveBeenCalledTimes(1);
			});
			const imported = mockImportBook.mock.calls[0][0] as BookImportCandidate;
			expect(imported.source).toBe('hardcover');
		});

		it('shows the Google supplement button when only hardcover results are returned', async () => {
			const hc = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover'
			});
			mockSearchStream.mockImplementation(makeStreamFinishing([hc]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			expect(screen.getByRole('button', { name: 'Search Google Books too' })).toBeInTheDocument();
		});

		it('merges Google supplement results into existing groups', async () => {
			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const gb = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'google_books',
				page_count: 480
			});
			let call = 0;
			mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
				call += 1;
				if (call === 1) {
					yield stageComplete([ol]);
					return;
				}
				yield* makeStreamFinishing([gb])(...args);
			});

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			expect(screen.queryByText(/result/)).not.toBeInTheDocument();
			expect(screen.queryByRole('button', { name: 'Show editions' })).not.toBeInTheDocument();

			await fireEvent.click(screen.getByRole('button', { name: 'Search Google Books too' }));

			await waitFor(() => {
				expect(screen.getByText('2 results')).toBeInTheDocument();
			});
			expect(screen.getByText('Google Books results added: 1')).toBeInTheDocument();
		});

		it('shows imported state for a group whose ISBN is already in the library', async () => {
			const existingBook = {
				id: 1,
				title: 'Dune',
				subtitle: null,
				author: 'Frank Herbert',
				authors: ['Frank Herbert'],
				isbn: '9780441013593',
				cover_url: null,
				publisher: null,
				published_year: null,
				page_count: null,
				language: null,
				tags: null,
				notes: null,
				blurb: null,
				rating: null,
				reading_status: 'want_to_read' as const,
				acquisition_status: 'owned' as const,
				medium: null,
				date_added: '2024-01-01T00:00:00Z',
				date_started: null,
				date_finished: null
			};
			vi.mocked(api.books.list).mockResolvedValue({ books: [existingBook], total: 1 });

			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const hc = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover'
			});
			mockSearchStream.mockImplementation(makeStreamFinishing([ol, hc]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			expect(screen.getByText('Already imported')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Imported' })).toBeDisabled();
		});

		it('treats an ISBN-10 library entry as imported for an ISBN-13 group', async () => {
			const existingBook = {
				id: 1,
				title: 'Dune',
				subtitle: null,
				author: 'Frank Herbert',
				authors: ['Frank Herbert'],
				isbn: '0441013597',
				cover_url: null,
				publisher: null,
				published_year: null,
				page_count: null,
				language: null,
				tags: null,
				notes: null,
				blurb: null,
				rating: null,
				reading_status: 'want_to_read' as const,
				acquisition_status: 'owned' as const,
				medium: null,
				date_added: '2024-01-01T00:00:00Z',
				date_started: null,
				date_finished: null
			};
			vi.mocked(api.books.list).mockResolvedValue({ books: [existingBook], total: 1 });

			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			mockSearchStream.mockImplementation(makeStreamFinishing([ol]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			expect(screen.getByRole('button', { name: 'Imported' })).toBeDisabled();
		});

		it('imports the default (first-with-cover) variant when no selection is made', async () => {
			const noCover = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const withCover = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover',
				cover_url: 'https://cover.jpg'
			});
			mockImportBook.mockResolvedValue({ id: 1, title: 'Dune' });
			mockSearchStream.mockImplementation(makeStreamFinishing([noCover, withCover]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});

			const acquisitionSelect = screen.getByRole('combobox', { name: /Possession/i });
			await fireEvent.change(acquisitionSelect, { target: { value: 'owned' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Add' }));

			await waitFor(() => {
				expect(mockImportBook).toHaveBeenCalledTimes(1);
			});
			const imported = mockImportBook.mock.calls[0][0] as BookImportCandidate;
			expect(imported.source).toBe('hardcover');
		});

		it('keeps a manually selected variant across the Google supplement', async () => {
			const ol = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library',
				cover_url: 'https://ol.jpg'
			});
			const hc = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover'
			});
			const gb = candidate(3, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'google_books'
			});
			let call = 0;
			mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
				call += 1;
				if (call === 1) {
					yield stageComplete([ol, hc]);
					return;
				}
				yield* makeStreamFinishing([gb])(...args);
			});
			mockImportBook.mockResolvedValue({ id: 1, title: 'Dune' });

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('2 results')).toBeInTheDocument();
			});

			// Select the hardcover variant.
			await fireEvent.click(screen.getByRole('button', { name: 'Show editions' }));
			await waitFor(() => {
				expect(screen.getByRole('button', { name: /^hardcover/ })).toBeInTheDocument();
			});
			await fireEvent.click(screen.getByRole('button', { name: /^hardcover/ }));

			// Google supplement appends a third variant.
			await fireEvent.click(screen.getByRole('button', { name: 'Search Google Books too' }));
			await waitFor(() => {
				expect(screen.getByText('3 results')).toBeInTheDocument();
			});

			const acquisitionSelect = screen.getByRole('combobox', { name: /Possession/i });
			await fireEvent.change(acquisitionSelect, { target: { value: 'owned' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Add' }));

			await waitFor(() => {
				expect(mockImportBook).toHaveBeenCalledTimes(1);
			});
			const imported = mockImportBook.mock.calls[0][0] as BookImportCandidate;
			expect(imported.source).toBe('hardcover');
		});

		it('resets group state on a new search', async () => {
			const dune = candidate(1, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			const duneHc = candidate(2, 'Dune', {
				isbn: '9780441013593',
				authors: ['Frank Herbert'],
				source: 'hardcover'
			});
			const duneMessiah = candidate(3, 'Dune Messiah', {
				isbn: '9780441013609',
				authors: ['Frank Herbert'],
				source: 'open_library'
			});
			mockSearchStream.mockImplementation(makeStreamFinishing([dune, duneHc, duneMessiah]));

			render(ImportSearch, {});
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.getByText('Dune')).toBeInTheDocument();
			});
			await fireEvent.click(screen.getByRole('button', { name: 'Show editions' }));
			expect(screen.getByRole('button', { name: 'Hide editions' })).toBeInTheDocument();

			// Second search with new results must collapse the group again.
			mockSearchStream.mockImplementation(makeStreamFinishing([duneMessiah]));
			await typeQueryAndSearch();

			await waitFor(() => {
				expect(screen.queryByText('Hide editions')).not.toBeInTheDocument();
				expect(screen.getByText('Dune Messiah')).toBeInTheDocument();
			});
			expect(screen.queryByText('Dune')).not.toBeInTheDocument();
		});
	});
});

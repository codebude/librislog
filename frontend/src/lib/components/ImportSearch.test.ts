import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import ImportSearch from './ImportSearch.svelte';
import type { BookImportCandidate, SearchStage } from '$lib/types';

const mockSearchStream = vi.fn();
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		import: {
			searchStream: (...args: unknown[]) => mockSearchStream(...args)
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

function candidate(id: number, title: string, source = 'open_library'): BookImportCandidate {
	return { id, title, author: null, authors: [], source } as unknown as BookImportCandidate;
}

function stageComplete(results: BookImportCandidate[]): SearchStage {
	return { stage: 'complete', results } as never;
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

// A stream that stays pending until either the delay elapses or the abort
// signal fires (rejecting with AbortError, mirroring how fetch behaves).
function makeStream({ delay = 10_000 } = {}) {
	return async function* (_q: unknown, _t: unknown, _m: unknown, signal?: AbortSignal) {
		await new Promise<void>((resolve, reject) => {
			onAbort(signal, () => reject(abortError()));
			setTimeout(resolve, delay);
		});
		yield stageComplete([candidate(1, 'Book 0')]);
	};
}

// A stream that immediately emits results and then stays pending until aborted.
function makeStreamWithResults(results: BookImportCandidate[]) {
	return async function* (_q: unknown, _t: unknown, _m: unknown, signal?: AbortSignal) {
		yield stageComplete(results);
		await new Promise<void>((_resolve, reject) => {
			onAbort(signal, () => reject(abortError()));
		});
	};
}

// A stream that emits results and then finishes normally.
function makeStreamFinishing(results: BookImportCandidate[]) {
	return async function* () {
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
	});

	afterEach(() => {
		cleanup();
	});

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
		const dune = candidate(1, 'Dune', 'open_library');
		const duneMessiah = candidate(2, 'Dune Messiah', 'open_library');
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

	it('Cancel during a Google supplement aborts it and keeps the main results', async () => {
		const dune = candidate(1, 'Dune', 'open_library');
		const duneMessiah = candidate(2, 'Dune Messiah', 'open_library');
		const signals: AbortSignal[] = [];
		let call = 0;
		mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
			const signal = args[3];
			if (signal) signals.push(signal);
			call += 1;
			if (call === 1) {
				yield stageComplete([dune, duneMessiah]);
				return;
			}
			yield* makeStreamWithResults([])(...args);
		});

		render(ImportSearch, {});
		await typeQueryAndSearch();

		await waitFor(() => {
			expect(screen.getByText('Dune')).toBeInTheDocument();
		});
		expect(screen.getByRole('button', { name: 'Search Google Books too' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Search Google Books too' }));
		await waitFor(() => {
			expect(signals).toHaveLength(2);
		});
		expect(signals[1]?.aborted).toBe(false);
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Searching Google Books...' })).toBeDisabled();

		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

		await waitFor(() => {
			expect(signals[1]?.aborted).toBe(true);
		});
		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Search Google Books too' })).toBeInTheDocument();
		});
		expect(screen.getByText('Dune')).toBeInTheDocument();
		expect(screen.getByText('Dune Messiah')).toBeInTheDocument();
		expect(mockToastsAdd).not.toHaveBeenCalled();
	});

	it('Google supplement merges new results and updates the added count', async () => {
		const dune = candidate(1, 'Dune', 'open_library');
		const encyclopedia = candidate(2, 'The Dune Encyclopedia', 'google_books');
		let call = 0;
		mockSearchStream.mockImplementation(async function* (...args: StreamArgs) {
			call += 1;
			if (call === 1) {
				yield stageComplete([dune]);
				return;
			}
			yield* makeStreamFinishing([encyclopedia])();
		});

		render(ImportSearch, {});
		await typeQueryAndSearch();

		await waitFor(() => {
			expect(screen.getByText('Dune')).toBeInTheDocument();
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Search Google Books too' }));

		await waitFor(() => {
			expect(screen.getByText('The Dune Encyclopedia')).toBeInTheDocument();
		});
		expect(screen.getByText('Dune')).toBeInTheDocument();
		expect(screen.getByText('Google Books results added: 1')).toBeInTheDocument();
		expect(mockToastsAdd).not.toHaveBeenCalled();
	});
});
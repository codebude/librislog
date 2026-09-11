import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import AddBookModal from './AddBookModal.svelte';
import type { BookImportCandidate, SearchStage } from '$lib/types';

// Mock api
const mockBooksCreate = vi.fn();
const mockBooksList = vi.fn(async () => ({ books: [], total: 0 }));
const mockSearchStream = vi.fn();
const mockImportBook = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		books: {
			create: (...args: unknown[]) => mockBooksCreate(...args),
			list: () => mockBooksList()
		},
		import: {
			searchStream: (...args: unknown[]) => mockSearchStream(...args),
			importBook: (...args: unknown[]) => mockImportBook(...args)
		}
	}
}));

// Mock toasts
const mockToastsAdd = vi.fn();

vi.mock('$lib/toasts', () => ({
	toasts: {
		add: (...args: unknown[]) => mockToastsAdd(...args),
		remove: vi.fn(),
		subscribe: writable([]).subscribe
	}
}));

// Mock html5-qrcode subpath imports for BarcodeScanner
vi.mock('html5-qrcode/esm/core', () => {
	const BaseLoggger = class {
		log() {} warn() {} logError() {} logErrors() {}
	};
	return {
		Html5QrcodeSupportedFormats: {
			EAN_13: 9, EAN_8: 10, UPC_A: 14, UPC_E: 15, CODE_128: 5, QR_CODE: 0
		},
		BaseLoggger
	};
});

vi.mock('html5-qrcode/esm/code-decoder', () => {
	const Html5QrcodeShim = class {
		decodeAsync: () => Promise<{ text: string }>;
		constructor() {
			this.decodeAsync = function () { return Promise.resolve({ text: '' }); };
		}
	};
	return { Html5QrcodeShim };
});

describe('AddBookModal', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it('does not render when open is false', () => {
		render(AddBookModal, { props: { open: false } });
		expect(screen.queryByRole('heading', { name: 'Add Book' })).not.toBeInTheDocument();
	});

	it('renders when open is true', () => {
		render(AddBookModal, { props: { open: true } });
		expect(screen.getByRole('heading', { name: 'Add Book' })).toBeInTheDocument();
	});

	it('shows correct title', () => {
		render(AddBookModal, { props: { open: true } });
		expect(screen.getByRole('heading', { name: 'Add Book' })).toBeInTheDocument();
	});

	it('has manual and import tabs', () => {
		render(AddBookModal, { props: { open: true } });
		expect(screen.getByRole('tab', { name: 'Manual' })).toBeInTheDocument();
		expect(screen.getByRole('tab', { name: 'Search & Import' })).toBeInTheDocument();
	});

	it('defaults to manual tab', () => {
		render(AddBookModal, { props: { open: true } });
		const manualTab = screen.getByRole('tab', { name: 'Manual' });
		expect(manualTab).toHaveClass('tab-active');
	});

	it('switches to import tab when clicked', async () => {
		render(AddBookModal, { props: { open: true } });
		const importTab = screen.getByRole('tab', { name: 'Search & Import' });
		await fireEvent.click(importTab);
		expect(importTab).toHaveClass('tab-active');
	});

	it('closes modal when close button clicked', async () => {
		render(AddBookModal, { props: { open: true } });
		const closeBtn = screen.getByRole('button', { name: /close/i });
		await fireEvent.click(closeBtn);
		expect(screen.queryByRole('heading', { name: 'Add Book' })).not.toBeInTheDocument();
	});

	it('renders form fields on manual tab', () => {
		render(AddBookModal, { props: { open: true } });
		expect(screen.getByLabelText(/Title/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Subtitle/)).toBeInTheDocument();
		expect(screen.getByText(/Author/)).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: 'ISBN' })).toBeInTheDocument();
		expect(screen.getByText(/Publisher/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Year/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Pages/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Language/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Rating/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Status/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Notes/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Description/)).toBeInTheDocument();
	});

	it('has status options in dropdown', () => {
		render(AddBookModal, { props: { open: true } });
		const select = screen.getByLabelText(/Status/);
		expect(select).toBeInTheDocument();
	});

	function fillAuthorAndPages(value: string) {
		const authorInput = screen.getByLabelText(/Author/);
		fireEvent.input(authorInput, { target: { value } });
		fireEvent.keyDown(authorInput, { key: 'Enter' });
		const pagesInput = screen.getByLabelText(/Pages/);
		fireEvent.input(pagesInput, { target: { value: '412' } });
		fireEvent.change(screen.getByRole('combobox', { name: /Possession/ }), { target: { value: 'owned' } });
	}

	it('submits form and calls api.books.create', async () => {
		mockBooksCreate.mockResolvedValue({ id: 1, title: 'Test Book' });
		const onAdded = vi.fn();

		render(AddBookModal, { props: { open: true, onAdded } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Test Book' } });
		fillAuthorAndPages('Frank Herbert');

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(mockBooksCreate).toHaveBeenCalledWith(
				expect.objectContaining({
					title: 'Test Book',
					authors: ['Frank Herbert'],
					page_count: 412,
					reading_status: 'want_to_read'
				})
			);
		});
	});

	it('calls onAdded and closes modal on successful submit', async () => {
		const book = { id: 1, title: 'Test Book' };
		mockBooksCreate.mockResolvedValue(book);
		const onAdded = vi.fn();

		render(AddBookModal, { props: { open: true, onAdded } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Test Book' } });
		fillAuthorAndPages('Frank Herbert');

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(onAdded).toHaveBeenCalledWith(book);
		});
		expect(screen.queryByRole('heading', { name: 'Add Book' })).not.toBeInTheDocument();
	});

	it('shows error toast when api.books.create fails', async () => {
		mockBooksCreate.mockRejectedValue(new Error('Network error'));

		render(AddBookModal, { props: { open: true } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Test Book' } });
		fillAuthorAndPages('Frank Herbert');

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(mockToastsAdd).toHaveBeenCalledWith('Network error', 'error');
		});
	});

	it('shows specific error toast for duplicate ISBN', async () => {
		mockBooksCreate.mockRejectedValue(new Error('error.isbnAlreadyExists'));

		render(AddBookModal, { props: { open: true } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Test Book' } });
		fillAuthorAndPages('Frank Herbert');

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(mockToastsAdd).toHaveBeenCalledWith(
				'This ISBN is already used by another book.',
				'error'
			);
		});
	});

	it('does not submit when title is empty', async () => {
		render(AddBookModal, { props: { open: true } });

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		expect(mockBooksCreate).not.toHaveBeenCalled();
	});

	it('does not submit when availability is not selected', async () => {
		render(AddBookModal, { props: { open: true } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Test Book' } });
		const authorInput = screen.getByLabelText(/Author/);
		await fireEvent.input(authorInput, { target: { value: 'Author' } });
		await fireEvent.keyDown(authorInput, { key: 'Enter' });
		const pagesInput = screen.getByLabelText(/Pages/);
		await fireEvent.input(pagesInput, { target: { value: '412' } });

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		expect(mockBooksCreate).not.toHaveBeenCalled();
	});

	it('submits acquisition_status in payload', async () => {
		mockBooksCreate.mockResolvedValue({ id: 1, title: 'Test Book' });
		render(AddBookModal, { props: { open: true } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Test Book' } });
		fillAuthorAndPages('Frank Herbert');

		const submitBtn = screen.getByRole('button', { name: 'Add Book' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(mockBooksCreate).toHaveBeenCalledWith(
				expect.objectContaining({ acquisition_status: 'owned' })
			);
		});
	});

	it('sets default status from prop', () => {
		render(AddBookModal, {
			props: { open: true, defaultStatus: 'currently_reading' }
		});

		const select = screen.getByLabelText(/Status/) as HTMLSelectElement;
		expect(select.value).toBe('currently_reading');
	});

	it('reset button clears form fields', async () => {
		render(AddBookModal, { props: { open: true } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Some Title' } });

		const resetBtn = screen.getByRole('button', { name: 'Clear Form' });
		await fireEvent.click(resetBtn);

		expect(titleInput).toHaveValue('');
	});

	describe('basket', () => {
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
				cover_url: null,
				publisher: null,
				published_year: options.published_year ?? null,
				page_count: null,
				language: null,
				tags: null,
				blurb: null,
				source: options.source ?? 'open_library'
			};
		}

		async function searchAndAddToBasket(title: string, id: number, expectedCount: number) {
			const book = candidate(id, title);
			mockSearchStream.mockImplementation(async function* () {
				yield { stage: 'complete', results: [book] } as SearchStage;
			});
			const importTab = screen.getByRole('tab', { name: 'Search & Import' });
			await fireEvent.click(importTab);
			const input = screen.getByPlaceholderText(/Search by title or author/);
			await fireEvent.input(input, { target: { value: title } });
			await fireEvent.click(screen.getByRole('button', { name: 'Search' }));
			await waitFor(() => {
				expect(screen.getByText(title)).toBeInTheDocument();
			});
			const acquisitionSelect = screen.getByRole('combobox', { name: /Possession/i });
			// happy-dom does not implement :checked for <option>, so Svelte 5's
			// bind_select_value cannot react to fireEvent.change on selects here.
			// We still drive the acquisitionStatus wiring; the metadata override
			// is verified via Playwright E2E, not unit tests.
			await fireEvent.change(acquisitionSelect, { target: { value: 'owned' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Add to Basket' }));
			await waitFor(() => {
				expect(screen.getByRole('tab', { name: /Basket/ }).textContent).toContain(String(expectedCount));
			});
		}

		beforeEach(() => {
			vi.clearAllMocks();
			mockBooksList.mockResolvedValue({ books: [], total: 0 });
			mockImportBook.mockResolvedValue({ id: 1, title: 'Test' });
		});

		it('shows a Basket tab with the added item count', async () => {
			render(AddBookModal, { props: { open: true, defaultStatus: 'want_to_read' } });
			await searchAndAddToBasket('Dune', 1, 1);

			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			expect(basketTab.textContent).toContain('1');
		});

		it('does not show a badge when the basket is empty', () => {
			render(AddBookModal, { props: { open: true } });
			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			expect(basketTab.querySelector('.badge')).toBeNull();
		});

		it('switches to the Basket tab and lists basket items', async () => {
			render(AddBookModal, { props: { open: true } });
			await searchAndAddToBasket('Dune', 1, 1);

			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			await fireEvent.click(basketTab);

			expect(screen.getByText('Dune')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Import Basket' })).toBeInTheDocument();
		});

		it('removes an item from the basket', async () => {
			render(AddBookModal, { props: { open: true } });
			await searchAndAddToBasket('Dune', 1, 1);

			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			await fireEvent.click(basketTab);

			const removeBtn = screen.getByRole('button', { name: /remove/i });
			await fireEvent.click(removeBtn);

			await waitFor(() => {
				expect(screen.getByRole('tab', { name: /Basket/ }).querySelector('.badge')).toBeNull();
			});
			expect(screen.queryByText('Dune')).not.toBeInTheDocument();
			expect(screen.getByText(/basket is empty/i)).toBeInTheDocument();
		});

		it('imports each basket item via api.import.importBook', async () => {
			const onAdded = vi.fn();
			render(AddBookModal, { props: { open: true, onAdded } });

			await searchAndAddToBasket('Dune', 1, 1);
			await searchAndAddToBasket('Dune Messiah', 2, 2);

			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			await fireEvent.click(basketTab);
			await fireEvent.click(screen.getByRole('button', { name: 'Import Basket' }));

			await waitFor(() => {
				expect(mockImportBook).toHaveBeenCalledTimes(2);
			});
			const firstCall = mockImportBook.mock.calls[0];
			expect(firstCall[0]).toMatchObject({ title: 'Dune' });
			expect(firstCall[1]).toBe('want_to_read');
			expect(firstCall[2]).toBe('owned');

			await waitFor(() => {
				expect(onAdded).toHaveBeenCalledTimes(2);
			});
		});

		it('keeps failed items in the basket on partial failure', async () => {
			mockImportBook
				.mockResolvedValueOnce({ id: 1, title: 'Dune' })
				.mockRejectedValueOnce(new Error('error.isbnAlreadyExists'));

			const onAdded = vi.fn();
			render(AddBookModal, { props: { open: true, onAdded } });

			await searchAndAddToBasket('Dune', 1, 1);
			await searchAndAddToBasket('Dune Messiah', 2, 2);

			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			await fireEvent.click(basketTab);
			await fireEvent.click(screen.getByRole('button', { name: 'Import Basket' }));

			await waitFor(() => {
				expect(onAdded).toHaveBeenCalledTimes(1);
			});
			await waitFor(() => {
				expect(screen.getByText('Dune Messiah')).toBeInTheDocument();
			});
			expect(screen.queryByText('Dune')).not.toBeInTheDocument();
		});

		it('closes the dialog on full basket import success', async () => {
			const onAdded = vi.fn();
			render(AddBookModal, { props: { open: true, onAdded } });

			await searchAndAddToBasket('Dune', 1, 1);

			const basketTab = screen.getByRole('tab', { name: /Basket/ });
			await fireEvent.click(basketTab);
			await fireEvent.click(screen.getByRole('button', { name: 'Import Basket' }));

			await waitFor(() => {
				expect(onAdded).toHaveBeenCalledTimes(1);
			});
			await waitFor(() => {
				expect(screen.queryByRole('heading', { name: 'Add Book' })).not.toBeInTheDocument();
			});
		});
	});
});

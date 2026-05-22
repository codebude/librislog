import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import AddBookModal from './AddBookModal.svelte';

// Mock api
const mockBooksCreate = vi.fn();
const mockBooksList = vi.fn(async () => []);

vi.mock('$lib/api', () => ({
	api: {
		books: {
			create: (...args: unknown[]) => mockBooksCreate(...args),
			list: () => mockBooksList()
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
		const closeBtn = screen.getByRole('button', { name: '✕' });
		await fireEvent.click(closeBtn);
		expect(screen.queryByRole('heading', { name: 'Add Book' })).not.toBeInTheDocument();
	});

	it('renders form fields on manual tab', () => {
		render(AddBookModal, { props: { open: true } });
		expect(screen.getByLabelText(/Title/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Subtitle/)).toBeInTheDocument();
		expect(screen.getByText(/Author/)).toBeInTheDocument();
		expect(screen.getByLabelText(/ISBN/)).toBeInTheDocument();
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
		const searchboxes = screen.getAllByRole('searchbox');
		const authorInput = searchboxes[0];
		fireEvent.input(authorInput, { target: { value } });
		const pagesInput = screen.getByLabelText(/Pages/);
		fireEvent.input(pagesInput, { target: { value: '412' } });
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
					author: 'Frank Herbert',
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
});

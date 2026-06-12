import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import BookDrawer from './BookDrawer.svelte';

const mockBooksUpdate = vi.fn(async (_id: number, _data: unknown) => ({ id: 1, title: 'Updated' }));
const mockTransitionStatus = vi.fn(async (_id: number, _data: unknown) => ({ book: { id: 1, title: 'Updated' }, date_conflict: null }));
const mockSuggestionsAuthors = vi.fn(async (_q: string) => ['Author 1']);
const mockSuggestionsPublishers = vi.fn(async (_q: string) => ['Publisher 1']);
const mockSuggestionsTags = vi.fn(async (_q: string) => ['Tag 1']);
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		books: {
			update: (id: number, data: unknown) => mockBooksUpdate(id, data),
			transitionStatus: (id: number, data: unknown) => mockTransitionStatus(id, data),
			suggestions: {
				authors: (q: string) => mockSuggestionsAuthors(q),
				publishers: (q: string) => mockSuggestionsPublishers(q),
				tags: (q: string) => mockSuggestionsTags(q)
			}
		}
	}
}));

vi.mock('html5-qrcode/esm/core', () => ({
	Html5QrcodeSupportedFormats: {
		EAN_13: 9, EAN_8: 10, UPC_A: 14, UPC_E: 15, CODE_128: 5, QR_CODE: 0
	},
	BaseLoggger: class { log() {} warn() {} logError() {} logErrors() {} }
}));

vi.mock('html5-qrcode/esm/code-decoder', () => {
	const Html5QrcodeShim = class {
		decodeAsync: () => Promise<{ text: string }>;
		constructor() {
			this.decodeAsync = function () { return Promise.resolve({ text: '' }); };
		}
	};
	return { Html5QrcodeShim };
});

vi.mock('$lib/toasts', () => ({
	toasts: {
		add: (...args: unknown[]) => mockToastsAdd(...args),
		remove: vi.fn(),
		subscribe: vi.fn()
	}
}));

const mockBook = {
	id: 1,
	title: 'Test Book',
	subtitle: 'Subtitle',
	author: 'Author Name',
	isbn: '9781234567890',
	publisher: 'Publisher',
	published_year: 2024,
	page_count: 300,
	language: 'en',
	tags: 'fiction',
	notes: '',
	blurb: '',
	rating: 4,
	reading_status: 'want_to_read' as const,
	date_added: '2024-01-01T00:00:00Z',
	date_started: null,
	date_finished: null,
	cover_url: null
};

describe('BookDrawer', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it('does not render when closed', () => {
		render(BookDrawer, { props: { book: mockBook, open: false } });
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('renders when open with book', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getByText('Test Book')).toBeInTheDocument();
	});

	it('renders form fields', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getByLabelText(/Title/)).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: /ISBN/ })).toBeInTheDocument();
		expect(screen.getByLabelText(/Year/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Pages/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Language/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Status/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Notes/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Description/)).toBeInTheDocument();
	});

	it('populates form with book data', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		const titleInput = screen.getByLabelText(/Title/) as HTMLInputElement;
		expect(titleInput.value).toBe('Test Book');
	});

	it('has save button', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
	});

	it('has cancel button', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
	});

	it('calls onSave after successful update', async () => {
		mockBooksUpdate.mockResolvedValue({ ...mockBook, title: 'Updated Title' });
		const onSave = vi.fn();

		render(BookDrawer, { props: { book: mockBook, open: true, onSave } });

		const titleInput = screen.getByLabelText(/Title/);
		await fireEvent.input(titleInput, { target: { value: 'Updated Title' } });

		const saveBtn = screen.getByRole('button', { name: 'Save' });
		await fireEvent.click(saveBtn);

		await waitFor(() => {
			expect(onSave).toHaveBeenCalled();
		});
	});

	it('closes drawer when cancel clicked', async () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
		await fireEvent.click(cancelBtn);
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('has close button', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		// Close button uses aria-label="Close" with ✕ as text
		expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
	});

	it('shows date inputs', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getByLabelText(/Date started/)).toBeInTheDocument();
		expect(screen.getByLabelText(/Date finished/)).toBeInTheDocument();
	});

	it('has rating selector', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getAllByRole('radio')).toHaveLength(5);
	});

	it('has cover picker', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		expect(screen.getByText('Cover')).toBeInTheDocument();
	});

	it('has google covers link', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		const link = screen.getByRole('link', { name: 'Google covers' });
		expect(link).toHaveAttribute('href', expect.stringContaining('google.com'));
	});

	it('has auto-search button disabled when no ISBN', () => {
		render(BookDrawer, { props: { book: { ...mockBook, isbn: '' }, open: true } });
		const autoSearchBtn = screen.getByRole('button', { name: 'Auto-search covers' });
		expect(autoSearchBtn).toBeDisabled();
	});

	it('has auto-search button enabled when ISBN present', () => {
		render(BookDrawer, { props: { book: mockBook, open: true } });
		const autoSearchBtn = screen.getByRole('button', { name: 'Auto-search covers' });
		expect(autoSearchBtn).not.toBeDisabled();
	});
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import BookDetailDialog from './BookDetailDialog.svelte';
import { setTimezone } from '$lib/stores/timezone';
import type { Book, ReadingProgressEntry } from '$lib/types';

vi.mock('svelte-chartjs', () => ({
	Line: vi.fn().mockImplementation(() => ({ default: {} })),
}));

const mockProgressList = vi.fn(async (_bookId: number): Promise<ReadingProgressEntry[]> => []);
const mockProgressCreate = vi.fn(async (_bookId: number, _page: number): Promise<ReadingProgressEntry> => ({ id: 1, book_id: _bookId, page: _page, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' }));
const mockProgressUpdate = vi.fn(async (_bookId: number, _entryId: number, _data: { created_at: string }): Promise<ReadingProgressEntry> => ({ id: _entryId, book_id: _bookId, page: 150, created_at: _data.created_at, updated_at: _data.created_at }));
const mockProgressDelete = vi.fn(async (_bookId: number, _entryId: number) => {});
const mockBooksDelete = vi.fn(async (_id: number) => {});
const mockBooksUpdate = vi.fn(async (_id: number, _data: Partial<Book>) => ({ ...mockBook, ..._data, id: _id }));
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		books: {
			update: (id: number, data: Partial<Book>) => mockBooksUpdate(id, data),
			progress: {
				list: (bookId: number) => mockProgressList(bookId),
				create: (bookId: number, page: number) => mockProgressCreate(bookId, page),
				update: (bookId: number, entryId: number, data: { created_at: string }) => mockProgressUpdate(bookId, entryId, data),
				delete: (bookId: number, entryId: number) => mockProgressDelete(bookId, entryId)
			},
			delete: (id: number) => mockBooksDelete(id)
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

const mockBook = {
	id: 1,
	title: 'Test Book',
	subtitle: 'A subtitle',
	author: 'Test Author',
	authors: ['Test Author'],
	isbn: '9781234567890',
	publisher: 'Test Publisher',
	published_year: 2024,
	page_count: 300,
	language: 'en',
	tags: 'fiction,classic',
	notes: 'Some notes',
	blurb: 'A long description that exceeds three hundred characters for testing truncation logic in the component. '.repeat(5),
	rating: 4,
	reading_status: 'currently_reading' as const,
	acquisition_status: 'owned' as const,
	date_added: '2024-01-01T00:00:00Z',
	date_started: '2024-02-01T00:00:00Z',
	date_finished: null,
	cover_url: 'http://example.com/cover.jpg'
};

describe('BookDetailDialog', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		setTimezone('UTC');
	});

	afterEach(() => {
		cleanup();
		setTimezone('UTC');
	});

	it('does not render when closed', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: false } });
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('renders book details when open', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('Test Book')).toBeInTheDocument();
		expect(screen.getByText('Test Author')).toBeInTheDocument();
	});

	it('shows cover image', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const img = screen.getByAltText('Cover of Test Book');
		expect(img).toHaveAttribute('src', 'http://example.com/cover.jpg');
	});

	it('shows reading status badge', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('Currently Reading')).toBeInTheDocument();
	});

	it('shows ISBN', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('9781234567890')).toBeInTheDocument();
	});

	it('shows rating with StarRating component', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getAllByRole('radio')).toHaveLength(5);
	});

	it('updates rating and shows toast when star is clicked', async () => {
		mockBooksUpdate.mockResolvedValue({ ...mockBook, rating: 3 });
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const stars = screen.getAllByRole('radio');
		await fireEvent.click(stars[2]); // click 3rd star (value=3)
		await waitFor(() => {
			expect(mockBooksUpdate).toHaveBeenCalledWith(1, { rating: 3 });
			expect(mockToastsAdd).toHaveBeenCalledWith('Rating saved', 'success', 2000);
		});
	});

	it('shows error toast on rating update failure', async () => {
		mockBooksUpdate.mockRejectedValue(new Error('Network error'));
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const stars = screen.getAllByRole('radio');
		await fireEvent.click(stars[4]); // click 5th star (value=5)
		await waitFor(() => {
			expect(mockToastsAdd).toHaveBeenCalledWith('Network error', 'error');
		});
	});

	it('shows book metadata fields', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('English')).toBeInTheDocument();
		expect(screen.getByText('Test Publisher')).toBeInTheDocument();
		expect(screen.getByText('2024')).toBeInTheDocument();
		expect(screen.getByText('300')).toBeInTheDocument();
	});

	it('shows dates', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('2024-02-01')).toBeInTheDocument();
	});

	it('shows tags', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('fiction')).toBeInTheDocument();
		expect(screen.getByText('classic')).toBeInTheDocument();
	});

	it('shows notes', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('Some notes')).toBeInTheDocument();
	});

	it('truncates long blurb with read more button', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const readMoreBtn = screen.getByRole('button', { name: 'Read more' });
		expect(readMoreBtn).toBeInTheDocument();
	});

	it('expands blurb when read more clicked', async () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const readMoreBtn = screen.getByRole('button', { name: 'Read more' });
		await fireEvent.click(readMoreBtn);
		expect(screen.getByRole('button', { name: 'Read less' })).toBeInTheDocument();
	});

	it('calls onEdit when edit button clicked', async () => {
		const onEdit = vi.fn();
		render(BookDetailDialog, { props: { book: mockBook, open: true, onEdit } });
		const editBtn = screen.getByRole('button', { name: 'Edit' });
		await fireEvent.click(editBtn);
		expect(onEdit).toHaveBeenCalledWith(mockBook);
	});

	it('shows delete confirmation flow', async () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const deleteBtn = screen.getByRole('button', { name: 'Delete' });
		await fireEvent.click(deleteBtn);
		expect(screen.getByRole('button', { name: 'Confirm?' })).toBeInTheDocument();
	});

	it('calls onDelete and closes on confirmed delete', async () => {
		mockBooksDelete.mockResolvedValue(undefined);
		const onDelete = vi.fn();
		render(BookDetailDialog, { props: { book: mockBook, open: true, onDelete } });

		await fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Confirm?' }));

		await waitFor(() => {
			expect(mockBooksDelete).toHaveBeenCalledWith(1);
			expect(onDelete).toHaveBeenCalledWith(1);
		});
	});

	it('shows progress section when page_count is set', () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		expect(screen.getByText('Reading Progress')).toBeInTheDocument();
	});

	it('shows message when no page_count', () => {
		render(BookDetailDialog, { props: { book: { ...mockBook, page_count: null }, open: true } });
		expect(screen.getByText('Please set total pages first.')).toBeInTheDocument();
	});

	it('loads progress on open', async () => {
		mockProgressList.mockResolvedValue([{ id: 1, book_id: 1, page: 150, created_at: '2024-03-01T00:00:00Z', updated_at: '2024-03-01T00:00:00Z' }]);
		render(BookDetailDialog, { props: { book: mockBook, open: true } });

		await waitFor(() => {
			expect(mockProgressList).toHaveBeenCalledWith(1);
		});
	});

	it('opens progress log modal', async () => {
		mockProgressList.mockResolvedValue([]);
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		await waitFor(() => expect(mockProgressList).toHaveBeenCalled());

		const logBtn = screen.getByRole('button', { name: 'Progress Log' });
		await fireEvent.click(logBtn);

		expect(screen.getByRole('dialog', { name: 'Progress Log' })).toBeInTheDocument();
	});

	it('closes when X button clicked', async () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const closeBtn = screen.getByRole('button', { name: 'Close' });
		await fireEvent.click(closeBtn);
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('closes on Escape', async () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('does not close when backdrop is clicked', async () => {
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		const dialog = screen.getByRole('dialog');
		const backdrop = dialog.previousElementSibling;
		expect(backdrop).toBeTruthy();
		await fireEvent.click(backdrop as Element);
		expect(screen.getByText('Test Book')).toBeInTheDocument();
	});

	it('closes nested progress log on Escape before closing the dialog', async () => {
		mockProgressList.mockResolvedValue([]);
		render(BookDetailDialog, { props: { book: mockBook, open: true } });
		await waitFor(() => expect(mockProgressList).toHaveBeenCalled());

		await fireEvent.click(screen.getByRole('button', { name: 'Progress Log' }));
		expect(screen.getByRole('dialog', { name: 'Progress Log' })).toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog', { name: 'Progress Log' })).not.toBeInTheDocument();
		expect(screen.getByText('Test Book')).toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('clamps current page input while typing', async () => {
		mockProgressList.mockResolvedValue([]);
		render(BookDetailDialog, { props: { book: mockBook, open: true } });

		await waitFor(() => expect(mockProgressList).toHaveBeenCalled());

		const input = document.querySelector('input[name="current-page"]') as HTMLInputElement;
		expect(input).toBeInTheDocument();

		await fireEvent.input(input, { target: { value: '999' } });
		expect(input.value).toBe('300');

		await fireEvent.input(input, { target: { value: '150' } });
		expect(input.value).toBe('150');

		await fireEvent.input(input, { target: { value: '-10' } });
		expect(input.value).toBe('0');
	});

	it('edits progress entry dates in the configured timezone', async () => {
		// Use a timezone well ahead of UTC so any browser-local interpretation
		// would shift the day.
		setTimezone('Asia/Tokyo');
		mockProgressList.mockResolvedValue([
			{ id: 1, book_id: 1, page: 150, created_at: '2026-09-08T15:00:00.000Z', updated_at: '2026-09-08T15:00:00.000Z' }
		]);
		render(BookDetailDialog, { props: { book: mockBook, open: true } });

		await waitFor(() => expect(mockProgressList).toHaveBeenCalled());
		await fireEvent.click(screen.getByRole('button', { name: 'Progress Log' }));
		const logDialog = await screen.findByRole('dialog', { name: 'Progress Log' });
		expect(logDialog).toBeInTheDocument();

		await fireEvent.click(within(logDialog).getByRole('button', { name: 'Edit' }));

		const input = within(logDialog).getByDisplayValue('2026-09-09T00:00') as HTMLInputElement;
		expect(input).toBeInTheDocument();

		// Shift by one minute and save. The new UTC instant must map back to
		// the same profile-timezone minute, proving the edit uses tz, not
		// browser-local time.
		await fireEvent.input(input, { target: { value: '2026-09-09T00:01' } });
		await fireEvent.click(within(logDialog).getByRole('button', { name: 'Save' }));

		await waitFor(() => {
			expect(mockProgressUpdate).toHaveBeenCalledWith(1, 1, { created_at: '2026-09-08T15:01:00.000Z' });
		});
	});
});

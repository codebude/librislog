import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import BookDetailDialog from './BookDetailDialog.svelte';

vi.mock('svelte-chartjs', () => ({
	Line: vi.fn().mockImplementation(() => ({ default: {} })),
}));

const mockProgressList = vi.fn(async () => []);
const mockProgressCreate = vi.fn(async (_bookId: number, _page: number) => ({ id: 1, book_id: _bookId, page: _page, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' }));
const mockProgressDelete = vi.fn(async () => {});
const mockBooksDelete = vi.fn(async () => {});
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		books: {
			progress: {
				list: (bookId: number) => mockProgressList(bookId),
				create: (bookId: number, page: number) => mockProgressCreate(bookId, page),
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
	date_added: '2024-01-01T00:00:00Z',
	date_started: '2024-02-01T00:00:00Z',
	date_finished: null,
	cover_url: 'http://example.com/cover.jpg'
};

describe('BookDetailDialog', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
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
});

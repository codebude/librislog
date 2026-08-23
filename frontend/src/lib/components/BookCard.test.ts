import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import BookCard from './BookCard.svelte';
import type { Book } from '$lib/types';

function mockBook(overrides?: Partial<Book>): Book {
	return {
		id: 1,
		title: 'The Test Book',
		subtitle: null,
		author: 'Jane Tester',
		isbn: '9781234567890',
		cover_url: 'http://localhost/cover.jpg',
		publisher: null,
		published_year: 2024,
		page_count: 300,
		language: 'en',
		tags: 'fiction,classic',
		notes: null,
		blurb: null,
		rating: 4,
		reading_status: 'currently_reading',
		acquisition_status: 'owned',
		date_added: '2024-01-01T00:00:00.000Z',
		date_started: null,
		date_finished: null,
		...overrides
	};
}

describe('BookCard', () => {
	it('shows an acquisition indicator only for books to acquire', () => {
		render(BookCard, {
			props: {
				book: mockBook({ reading_status: 'want_to_read', acquisition_status: 'to_acquire' }),
				onClick: vi.fn()
			}
		});

		expect(screen.getByLabelText('Needs to be acquired')).toBeInTheDocument();
	});
	it('renders title and author', () => {
		render(BookCard, { props: { book: mockBook(), onClick: vi.fn() } });

		expect(screen.getByText('The Test Book')).toBeInTheDocument();
		expect(screen.getByText('Jane Tester')).toBeInTheDocument();
	});

	it('shows cover image when cover_url is present', () => {
		render(BookCard, { props: { book: mockBook(), onClick: vi.fn() } });

		const img = screen.getByAltText('Cover of The Test Book');
		expect(img).toBeInTheDocument();
		expect(img).toHaveAttribute('src', 'http://localhost/cover.jpg');
	});

	it('shows placeholder when cover_url is missing', () => {
		render(BookCard, {
			props: { book: mockBook({ cover_url: null }), onClick: vi.fn() }
		});

		expect(screen.queryByAltText(/Cover of/)).not.toBeInTheDocument();
	});

	it('shows reading status badge', () => {
		render(BookCard, { props: { book: mockBook(), onClick: vi.fn() } });

		expect(screen.getByText('Currently Reading')).toBeInTheDocument();
	});

	it('shows progress bar when currentPage is greater than 0', () => {
		render(BookCard, {
			props: { book: mockBook(), onClick: vi.fn(), currentPage: 150 }
		});

		const progress = document.querySelector('.bg-primary.rounded-full');
		expect(progress).toBeInTheDocument();
		expect(progress).toHaveAttribute('style', expect.stringContaining('width: 50%'));
	});

	it('does not show progress bar when currentPage is 0', () => {
		render(BookCard, {
			props: { book: mockBook(), onClick: vi.fn(), currentPage: 0 }
		});

		expect(document.querySelector('.bg-primary.rounded-full')).not.toBeInTheDocument();
	});

	it('does not show progress bar when page_count is null', () => {
		render(BookCard, {
			props: { book: mockBook({ page_count: null }), onClick: vi.fn(), currentPage: 150 }
		});

		expect(document.querySelector('.bg-primary.rounded-full')).not.toBeInTheDocument();
	});

	it('calls onClick with the book when card is clicked', async () => {
		const book = mockBook();
		const onClick = vi.fn();
		render(BookCard, { props: { book, onClick } });

		const card = screen.getByText('The Test Book').closest('button');
		expect(card).toBeTruthy();
		await fireEvent.click(card!);

		expect(onClick).toHaveBeenCalledTimes(1);
		expect(onClick).toHaveBeenCalledWith(book);
	});

	it('renders all status badges correctly', () => {
		const statuses: Array<{ status: Book['reading_status']; label: string; className: string }> = [
			{ status: 'want_to_read', label: 'Want to Read', className: 'badge-info' },
			{ status: 'currently_reading', label: 'Currently Reading', className: 'badge-warning' },
			{ status: 'read', label: 'Read', className: 'badge-success' },
			{ status: 'did_not_finish', label: 'Did Not Finish', className: 'badge-error' }
		];

		for (const { status, label } of statuses) {
			const { container } = render(BookCard, {
				props: { book: mockBook({ reading_status: status }), onClick: vi.fn() }
			});
			expect(screen.getByText(label)).toBeInTheDocument();
			// Clean up between renders
			container.remove();
		}
	});

	it('does not show author when null', () => {
		render(BookCard, {
			props: { book: mockBook({ author: null }), onClick: vi.fn() }
		});
		expect(screen.queryByText('Jane Tester')).not.toBeInTheDocument();
	});

	it('shows progress bar at 100%', () => {
		render(BookCard, {
			props: { book: mockBook(), onClick: vi.fn(), currentPage: 300 }
		});
		const progress = document.querySelector('.bg-primary.rounded-full');
		expect(progress).toHaveAttribute('style', expect.stringContaining('width: 100%'));
	});
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import RatedBooksSection from './RatedBooksSection.svelte';
import type { TopRatedBook } from '$lib/types';

const mockBooksGet = vi.fn(async (_id: number) => ({
	id: _id,
	title: 'Test Book',
	author: 'Test Author',
	cover_url: 'http://example.com/cover.jpg',
	rating: 4,
	reading_status: 'read' as const,
	date_added: '2024-01-01T00:00:00Z',
	page_count: 300,
	isbn: null,
	publisher: null,
	published_year: null,
	language: null,
	tags: null,
	blurb: null,
	notes: null,
	subtitle: null
}));

const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		books: {
			get: (id: number) => mockBooksGet(id)
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

vi.mock('$lib/i18n', () => ({
	_: {
		subscribe: (run: (value: (key: string, opts?: Record<string, unknown>) => string) => void) => {
			run((key: string, opts?: Record<string, unknown>) => {
				if (opts?.values) {
					return key.replace(/\{(\w+)\}/g, (_m: string, k: string) => String((opts.values as Record<string, unknown>)[k] ?? ''));
				}
				return key;
			});
			return () => {};
		}
	},
	locale: {
		subscribe: (run: (value: string) => void) => {
			run('en');
			return () => {};
		}
	}
}));

function makeBook(id: number, rating: number, title?: string): TopRatedBook {
	return {
		book_id: id,
		title: title ?? `Book ${id}`,
		author: `Author ${id}`,
		authors: [`Author ${id}`],
		rating,
		reading_status: 'read',
		cover_url: `http://example.com/cover${id}.jpg`
	};
}

describe('RatedBooksSection', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the section title', () => {
		const books = [makeBook(1, 5)];
		render(RatedBooksSection, { props: { title: 'Top Rated', books } });
		expect(screen.getByText('Top Rated')).toBeInTheDocument();
	});

	it('shows first 10 books with Show More button', () => {
		const books = Array.from({ length: 12 }, (_, i) => makeBook(i + 1, 5, `Book ${i + 1}`));
		render(RatedBooksSection, { props: { title: 'Top Rated', books } });

		for (let i = 1; i <= 10; i++) {
			expect(screen.getByText(`Book ${i}`)).toBeInTheDocument();
		}
		expect(screen.queryByText('Book 11')).not.toBeInTheDocument();
		expect(screen.queryByText('Book 12')).not.toBeInTheDocument();
		expect(screen.getByText('statistics.showMore')).toBeInTheDocument();
	});

	it('shows all books after clicking Show More', async () => {
		const books = Array.from({ length: 12 }, (_, i) => makeBook(i + 1, 5, `Book ${i + 1}`));
		render(RatedBooksSection, { props: { title: 'Top Rated', books } });

		await fireEvent.click(screen.getByText('statistics.showMore'));

		for (let i = 1; i <= 12; i++) {
			expect(screen.getByText(`Book ${i}`)).toBeInTheDocument();
		}
		expect(screen.queryByText('statistics.showMore')).not.toBeInTheDocument();
	});

	it('shows no data message when books array is empty', () => {
		render(RatedBooksSection, { props: { title: 'Top Rated', books: [] } });
		expect(screen.getByText('statistics.noData')).toBeInTheDocument();
	});

	it('calls api.books.get when a cover is clicked', async () => {
		const books = [makeBook(42, 5, 'Clickable Book')];
		const { container } = render(RatedBooksSection, { props: { title: 'Top Rated', books } });

		const coverBtn = container.querySelector('button[aria-label="Clickable Book"]') as HTMLButtonElement;
		expect(coverBtn).not.toBeNull();
		await fireEvent.click(coverBtn);

		await waitFor(() => {
			expect(mockBooksGet).toHaveBeenCalledWith(42);
		});
	});

	it('shows rank badges with correct numbers', () => {
		const books = [
			makeBook(1, 5, 'A'),
			makeBook(2, 5, 'B'),
			makeBook(3, 5, 'C')
		];
		render(RatedBooksSection, { props: { title: 'Top Rated', books } });

		const badges = screen.getAllByText('statistics.rankedNumber');
		expect(badges).toHaveLength(3);
	});

	it('handles API error when clicking a cover', async () => {
		mockBooksGet.mockRejectedValueOnce(new Error('Network error'));
		const books = [makeBook(1, 5, 'Error Book')];
		const { container } = render(RatedBooksSection, { props: { title: 'Top Rated', books } });

		const coverBtn = container.querySelector('button[aria-label="Error Book"]') as HTMLButtonElement;
		expect(coverBtn).not.toBeNull();
		await fireEvent.click(coverBtn);

		await waitFor(() => {
			expect(mockToastsAdd).toHaveBeenCalledWith('Network error', 'error');
		});
	});
});

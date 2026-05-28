import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import SearchPage from './+page.svelte';
import type { Book } from '$lib/types';

const mockPage = vi.hoisted(() => {
	const subscribers = new Set<(value: unknown) => void>();
	let state = { url: new URL('http://localhost:5173/search'), params: {}, route: { id: null } };

	return {
		subscribe(run: (value: unknown) => void) {
			run(state);
			subscribers.add(run);
			return () => subscribers.delete(run);
		},
		setUrl(url: string) {
			state = { url: new URL(url), params: {}, route: { id: null } };
			subscribers.forEach((fn) => fn(state));
		}
	};
});

vi.mock('$app/stores', () => ({
	page: { subscribe: mockPage.subscribe },
	navigating: { subscribe: vi.fn() }
}));

const mockGoto = vi.fn();
vi.mock('$app/navigation', () => ({
	goto: (...args: unknown[]) => mockGoto(...args),
	beforeNavigate: () => {},
	afterNavigate: () => {},
	onNavigate: () => () => {}
}));

const mockBooksList = vi.fn();
vi.mock('$lib/api', () => ({
	api: {
		books: {
			list: (...args: unknown[]) => mockBooksList(...args)
		}
	}
}));

function createMockBook(id: number, overrides?: Partial<Book>): Book {
	return {
		id,
		title: `Book ${id}`,
		subtitle: null,
		author: 'Test Author',
		isbn: null,
		cover_url: null,
		publisher: null,
		published_year: null,
		page_count: 100,
		language: null,
		tags: null,
		notes: null,
		blurb: null,
		rating: null,
		reading_status: 'want_to_read',
		date_added: '2025-01-01T00:00:00Z',
		date_started: null,
		date_finished: null,
		...overrides
	};
}

describe('SearchPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockPage.setUrl('http://localhost:5173/search');
	});

	afterEach(() => {
		cleanup();
	});

	it('renders search input with placeholder', () => {
		render(SearchPage);
		expect(screen.getByPlaceholderText('Search books...')).toBeInTheDocument();
	});

	it('reads q from URL and performs search on mount', async () => {
		mockPage.setUrl('http://localhost:5173/search?q=Dune');

		mockBooksList.mockResolvedValue({
			total: 1,
			books: [createMockBook(1, { title: 'Dune', author: 'Frank Herbert' })]
		});

		render(SearchPage);

		await waitFor(() => {
			expect(mockBooksList).toHaveBeenCalledWith(
				expect.objectContaining({ q: 'Dune', offset: 0, limit: 40 })
			);
		});
	});

	it('displays search results', async () => {
		mockPage.setUrl('http://localhost:5173/search?q=Dune');

		mockBooksList.mockResolvedValue({
			total: 1,
			books: [createMockBook(1, { title: 'Dune', author: 'Frank Herbert' })]
		});

		render(SearchPage);

		await waitFor(() => {
			expect(screen.getByText('Dune')).toBeInTheDocument();
			expect(screen.getByText('Frank Herbert')).toBeInTheDocument();
		});
	});

	it('shows results count', async () => {
		mockPage.setUrl('http://localhost:5173/search?q=Dune');

		mockBooksList.mockResolvedValue({
			total: 3,
			books: [
				createMockBook(1, { title: 'Dune' }),
				createMockBook(2, { title: 'Dune Messiah' }),
				createMockBook(3, { title: 'Children of Dune' })
			]
		});

		render(SearchPage);

		await waitFor(() => {
			expect(screen.getByText('3')).toBeInTheDocument();
		});
	});

	it('shows no results message when API returns empty', async () => {
		mockPage.setUrl('http://localhost:5173/search?q=xyzzy');

		mockBooksList.mockResolvedValue({
			total: 0,
			books: []
		});

		render(SearchPage);

		await waitFor(() => {
			expect(screen.getByText('No results found for "xyzzy"')).toBeInTheDocument();
		});
	});

	it('shows loading spinner while searching', async () => {
		mockPage.setUrl('http://localhost:5173/search?q=Dune');

		mockBooksList.mockReturnValue(new Promise(() => {}));

		render(SearchPage);

		await waitFor(() => {
			expect(document.querySelector('.loading-spinner')).toBeInTheDocument();
		});
	});

	it('clears input and results when clear button clicked', async () => {
		mockPage.setUrl('http://localhost:5173/search?q=test');

		mockBooksList.mockResolvedValue({
			total: 1,
			books: [createMockBook(1, { title: 'Test Book' })]
		});

		render(SearchPage);

		await waitFor(() => {
			expect(screen.getByText('Test Book')).toBeInTheDocument();
		});

		const clearBtn = screen.getByRole('button', { name: /clear/i });
		await fireEvent.click(clearBtn);

		const input = screen.getByPlaceholderText('Search books...') as HTMLInputElement;
		expect(input).toHaveValue('');
		expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
	});

	it('debounces search while typing', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });

		render(SearchPage);
		const input = screen.getByPlaceholderText('Search books...');

		mockBooksList.mockResolvedValue({ total: 0, books: [] });

		await fireEvent.input(input, { target: { value: 'd' } });
		await vi.advanceTimersByTimeAsync(200);
		await fireEvent.input(input, { target: { value: 'du' } });
		await vi.advanceTimersByTimeAsync(200);
		await fireEvent.input(input, { target: { value: 'dune' } });

		expect(mockBooksList).not.toHaveBeenCalled();

		await vi.advanceTimersByTimeAsync(300);

		expect(mockBooksList).toHaveBeenCalledTimes(1);
		expect(mockBooksList).toHaveBeenCalledWith(
			expect.objectContaining({ q: 'dune', offset: 0 })
		);

		vi.useRealTimers();
	});

	it('navigates to search URL on Enter', async () => {
		render(SearchPage);
		const input = screen.getByPlaceholderText('Search books...');
		await fireEvent.input(input, { target: { value: 'Neuromancer' } });

		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(mockGoto).toHaveBeenCalledWith(
			'/search?q=Neuromancer',
			expect.objectContaining({ replaceState: true })
		);
	});

	it('loads more results when load more is clicked', async () => {
		const firstPage = Array.from({ length: 40 }, (_, i) =>
			createMockBook(i + 1, { title: `Book ${i + 1}` })
		);
		const secondPage = Array.from({ length: 40 }, (_, i) =>
			createMockBook(41 + i, { title: `Book ${41 + i}` })
		);

		mockBooksList.mockResolvedValueOnce({ total: 80, books: firstPage });
		mockBooksList.mockResolvedValueOnce({ total: 80, books: secondPage });

		mockPage.setUrl('http://localhost:5173/search?q=book');

		render(SearchPage);

		await waitFor(() => {
			expect(screen.getByText('Book 1')).toBeInTheDocument();
		});
		expect(screen.queryByText('Book 41')).not.toBeInTheDocument();

		expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /load more/i }));

		await waitFor(() => {
			expect(screen.getByText('Book 41')).toBeInTheDocument();
		});
		expect(screen.getByText('Book 1')).toBeInTheDocument();

		expect(mockBooksList).toHaveBeenCalledTimes(2);
		expect(mockBooksList).toHaveBeenLastCalledWith(
			expect.objectContaining({ offset: 40, limit: 40, q: 'book' })
		);
	});

	it('shows back button', () => {
		render(SearchPage);
		expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument();
	});
});

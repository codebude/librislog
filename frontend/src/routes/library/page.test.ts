import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import LibraryPage from './+page.svelte';
import type { Book, LibraryStats } from '$lib/types';

const mockPage = vi.hoisted(() => {
	const subscribers = new Set<(value: unknown) => void>();
	let state = { url: new URL('http://localhost:5173/library'), params: {}, route: { id: null } };

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
const mockBooksStats = vi.fn();
const mockProgressLatest = vi.fn();
vi.mock('$lib/api', () => ({
	api: {
		books: {
			list: (...args: unknown[]) => mockBooksList(...args),
			stats: (...args: unknown[]) => mockBooksStats(...args),
			progress: { latest: (...args: unknown[]) => mockProgressLatest(...args) }
		}
	}
}));

// Stub child components so the test isolates the page's own tab/search/sort logic
// without pulling in chartjs, barcode scanners, or dialogs that break under jsdom.
function stubComponent(tag: string) {
	return () => ({
		render: () => ({ html: `<div data-stub="${tag}"></div>`, css: { code: '', map: null }, head: '' })
	});
}
vi.mock('$lib/components/BookCard.svelte', () => ({ default: stubComponent('BookCard') }));
vi.mock('$lib/components/BookListItem.svelte', () => ({ default: stubComponent('BookListItem') }));
vi.mock('$lib/components/BookDetailDialog.svelte', () => ({ default: stubComponent('BookDetailDialog') }));
vi.mock('$lib/components/BookDrawer.svelte', () => ({ default: stubComponent('BookDrawer') }));
vi.mock('$lib/components/AddBookModal.svelte', () => ({ default: stubComponent('AddBookModal') }));
vi.mock('$lib/components/SearchBar.svelte', () => ({ default: stubComponent('SearchBar') }));
vi.mock('$lib/components/SearchHelp.svelte', () => ({ default: stubComponent('SearchHelp') }));

function createMockBook(id: number, overrides?: Partial<Book>): Book {
	return {
		id,
		title: `Book ${id}`,
		subtitle: null,
		author: 'Test Author',
		authors: ['Test Author'],
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
		acquisition_status: 'owned',
		date_added: '2025-01-01T00:00:00Z',
		date_started: null,
		date_finished: null,
		...overrides
	};
}

function createMockStats(overrides?: Partial<LibraryStats>): LibraryStats {
	return {
		total_books: 12,
		books_want_to_read: 7,
		books_reading: 1,
		books_read: 3,
		books_did_not_finish: 1,
		...overrides
	};
}

describe('LibraryPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockPage.setUrl('http://localhost:5173/library');
		mockBooksStats.mockResolvedValue(createMockStats());
		mockBooksList.mockResolvedValue({ total: 0, books: [] });
		mockProgressLatest.mockResolvedValue([]);
	});

	afterEach(() => {
		cleanup();
	});

	it('renders all five tabs including All Books with total count', async () => {
		render(LibraryPage);

		await waitFor(() => {
			expect(screen.getByRole('tab', { name: 'Want to Read (7)' })).toBeInTheDocument();
		});
		expect(screen.getByRole('tab', { name: 'Currently Reading (1)' })).toBeInTheDocument();
		expect(screen.getByRole('tab', { name: 'Read (3)' })).toBeInTheDocument();
		expect(screen.getByRole('tab', { name: 'Did Not Finish (1)' })).toBeInTheDocument();
		expect(screen.getByRole('tab', { name: 'All Books (12)' })).toBeInTheDocument();
	});

	it('fetches books without a status filter when status=all', async () => {
		mockPage.setUrl('http://localhost:5173/library?status=all');
		mockBooksList.mockResolvedValue({
			total: 2,
			books: [createMockBook(1, { reading_status: 'read' }), createMockBook(2, { reading_status: 'want_to_read' })]
		});

		render(LibraryPage);

		await waitFor(() => {
			expect(mockBooksList).toHaveBeenCalled();
		});
		const params = mockBooksList.mock.calls[0][0];
		expect(params.status).toBeUndefined();
		expect(screen.getByRole('heading', { name: 'All Books' })).toBeInTheDocument();
	});

	it('fetches books with a status filter on a status tab', async () => {
		mockPage.setUrl('http://localhost:5173/library?status=want_to_read');

		render(LibraryPage);

		await waitFor(() => {
			expect(mockBooksList).toHaveBeenCalled();
		});
		const params = mockBooksList.mock.calls[0][0];
		expect(params.status).toBe('want_to_read');
	});

	it('clicking the All Books tab navigates to status=all', async () => {
		render(LibraryPage);

		const allTab = await screen.findByRole('tab', { name: /All Books/ });
		await fireEvent.click(allTab);

		expect(mockGoto).toHaveBeenCalledWith('/library?status=all');
	});

	it('hides smart sort and keeps sort selects enabled on the All tab', async () => {
		mockPage.setUrl('http://localhost:5173/library?status=all');

		const { container } = render(LibraryPage);

		await waitFor(() => {
			expect(mockBooksList).toHaveBeenCalled();
		});
		expect(container.querySelector('input[name="smart-sort"]')).toBeNull();
		const sortField = container.querySelector('select[name="sort-field"]') as HTMLSelectElement;
		const sortOrder = container.querySelector('select[name="sort-order"]') as HTMLSelectElement;
		expect(sortField.disabled).toBe(false);
		expect(sortOrder.disabled).toBe(false);
	});

	it('shows smart sort on a status tab', async () => {
		render(LibraryPage);

		const { container } = render(LibraryPage);
		await waitFor(() => {
			expect(mockBooksList).toHaveBeenCalled();
		});
		expect(container.querySelector('input[name="smart-sort"]')).not.toBeNull();
	});
});
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import DataHygienePage from './+page.svelte';
import type { HygieneMissingBook, HygieneAttribute } from '$lib/types';

const mockListMissing = vi.fn();
const mockBatchUpdate = vi.fn();
vi.mock('$lib/api', () => ({
	api: {
		hygiene: {
			listMissing: (...args: unknown[]) => mockListMissing(...args),
			batchUpdate: (...args: unknown[]) => mockBatchUpdate(...args),
		}
	}
}));

const mockToastAdd = vi.fn();
vi.mock('$lib/toasts', () => ({
	toasts: {
		add: (...args: unknown[]) => mockToastAdd(...args),
		subscribe: vi.fn(),
	}
}));

vi.mock('$lib/errors', () => ({
	localizeError: (_err: unknown, _translate: unknown, fallback: string) => fallback,
}));

function mockBook(id: number, overrides?: Partial<HygieneMissingBook>): HygieneMissingBook {
	return {
		id,
		title: `Book ${id}`,
		author: id % 2 === 0 ? `Author ${id}` : null,
		isbn: id % 3 === 0 ? `978${String(id).padStart(10, '0')}` : null,
		publisher: id % 2 === 0 ? 'Publisher' : null,
		published_year: null,
		blurb: null,
		language: null,
		subtitle: null,
		page_count: 0,
		cover_url: null,
		missing_attributes: overrides?.missing_attributes ?? ['author'],
		...overrides,
	};
}

const emptyPerAttribute = {
	author: 0, isbn: 0, publisher: 0, published_year: 0,
	blurb: 0, language: 0, subtitle: 0, page_count: 0, cover_url: 0,
};

describe('DataHygienePage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockListMissing.mockResolvedValue({
			books: [],
			total: 0,
			total_missing_per_attribute: { ...emptyPerAttribute },
		});
	});

	afterEach(() => {
		cleanup();
	});

	it('renders title and description', async () => {
		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Data Hygiene')).toBeInTheDocument();
		});
		expect(screen.getByText('Find and fix books with missing metadata in your library.')).toBeInTheDocument();
	});

	it('shows loading state initially', () => {
		mockListMissing.mockReturnValue(new Promise(() => {}));
		render(DataHygienePage);
		expect(screen.getByText('Checking your library...')).toBeInTheDocument();
	});

	it('loads data on mount with default attributes', async () => {
		render(DataHygienePage);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(1);
		});
		expect(mockListMissing).toHaveBeenCalledWith({
			attributes: [
				'author', 'isbn', 'publisher', 'published_year',
				'blurb', 'language', 'subtitle', 'page_count', 'cover_url',
			],
			match: 'any',
			offset: 0,
			limit: 50,
		});
	});

	it('displays all 9 attribute chips', async () => {
		render(DataHygienePage);

		const chips = await screen.findAllByRole('button');
		const attrChips = chips.filter(c =>
			/Author|ISBN|Publisher|Year|Description|Language|Subtitle|Page count|Cover/.test(c.textContent || '')
		);
		expect(attrChips).toHaveLength(9);
	});

	it('shows per-attribute missing counts on chips', async () => {
		mockListMissing.mockResolvedValue({
			books: [mockBook(1)],
			total: 1,
			total_missing_per_attribute: {
				author: 5, isbn: 3, publisher: 0, published_year: 2,
				blurb: 1, language: 0, subtitle: 0, page_count: 0, cover_url: 4,
			},
		});

		render(DataHygienePage);

		await waitFor(() => {
			const chips = screen.getAllByText('Author').filter(el => el.closest('.btn'));
			expect(chips.length).toBeGreaterThanOrEqual(1);
		});

		expect(screen.getByText('(5)')).toBeInTheDocument();
		expect(screen.getByText('(3)')).toBeInTheDocument();
	});

	it('toggling attribute chip reloads data with updated attributes', async () => {
		render(DataHygienePage);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(1);
		});

		const authorBtn = screen.getAllByText('Author').filter(el => el.closest('.btn'))[0];
		await fireEvent.click(authorBtn);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(2);
		});

		const secondCall = mockListMissing.mock.calls[1][0];
		expect(secondCall.attributes).toEqual(['author']);
		expect(secondCall.offset).toBe(0);
	});

	it('toggle match mode between any and all', async () => {
		render(DataHygienePage);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(1);
		});

		const matchBtn = screen.getByText('Match any');
		await fireEvent.click(matchBtn);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(2);
		});
		expect(mockListMissing.mock.calls[1][0].match).toBe('all');

		const allBtn = screen.getByText('Match all');
		await fireEvent.click(allBtn);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(3);
		});
		expect(mockListMissing.mock.calls[2][0].match).toBe('any');
	});

	it('renders book rows from API response', async () => {
		mockListMissing.mockResolvedValue({
			books: [
				mockBook(1, { title: 'Dune', author: null }),
				mockBook(2, { title: 'Neuromancer', author: 'William Gibson' }),
			],
			total: 2,
			total_missing_per_attribute: {
				author: 2, isbn: 0, publisher: 0, published_year: 0,
				blurb: 0, language: 0, subtitle: 0, page_count: 0, cover_url: 0,
			},
		});

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Dune')).toBeInTheDocument();
		});
		expect(screen.getByText('Neuromancer')).toBeInTheDocument();
	});

	it('shows missing attribute badges per book', async () => {
		mockListMissing.mockResolvedValue({
			books: [mockBook(1, { missing_attributes: ['author', 'isbn'] })],
			total: 1,
			total_missing_per_attribute: {
				author: 1, isbn: 1, publisher: 0, published_year: 0,
				blurb: 0, language: 0, subtitle: 0, page_count: 0, cover_url: 0,
			},
		});

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Book 1')).toBeInTheDocument();
		});

		const badges = screen.getAllByText('Author').filter(
			el => el.closest('.badge')
		);
		expect(badges.length).toBeGreaterThanOrEqual(1);
	});

	it('loads more books on load more click', async () => {
		const firstPage = Array.from({ length: 50 }, (_, i) =>
			mockBook(i + 1, { missing_attributes: ['author'] })
		);

		mockListMissing.mockResolvedValueOnce({
			books: firstPage,
			total: 60,
			total_missing_per_attribute: { ...emptyPerAttribute, author: 60 },
		});

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Book 1')).toBeInTheDocument();
			expect(screen.queryByText('Book 51')).not.toBeInTheDocument();
		});

		mockListMissing.mockResolvedValueOnce({
			books: [mockBook(51, { missing_attributes: ['author'] })],
			total: 60,
			total_missing_per_attribute: { ...emptyPerAttribute, author: 60 },
		});

		const loadMoreBtn = screen.getByText(/load more/i);
		await fireEvent.click(loadMoreBtn);

		await waitFor(() => {
			expect(screen.getByText('Book 51')).toBeInTheDocument();
		});
		expect(mockListMissing).toHaveBeenCalledTimes(2);
	});

	it('hides load more when all books loaded', async () => {
		mockListMissing.mockResolvedValue({
			books: [mockBook(1, { missing_attributes: ['author'] })],
			total: 1,
			total_missing_per_attribute: { ...emptyPerAttribute, author: 1 },
		});

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Book 1')).toBeInTheDocument();
		});

		expect(screen.queryByText(/load more/i)).not.toBeInTheDocument();
	});

	it('shows all-complete success alert when no missing books', async () => {
		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Your library is in great shape! All books have complete metadata.')).toBeInTheDocument();
		});
	});

	it('shows error alert when API call fails', async () => {
		mockListMissing.mockRejectedValue(new Error('Network error'));

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Failed to load data.')).toBeInTheDocument();
		});
	});

	it('dismisses error alert', async () => {
		mockListMissing.mockRejectedValue(new Error('Network error'));

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Failed to load data.')).toBeInTheDocument();
		});

		const closeBtn = screen.getByLabelText('Close');
		await fireEvent.click(closeBtn);

		expect(screen.queryByText('Failed to load data.')).not.toBeInTheDocument();
	});

	it('shows filtered success message when attributes selected', async () => {
		let apiCallCount = 0;
		mockListMissing.mockImplementation(() => {
			apiCallCount++;
			if (apiCallCount > 1) {
				return Promise.resolve({
					books: [],
					total: 0,
					total_missing_per_attribute: { ...emptyPerAttribute },
				});
			}
			return Promise.resolve({
				books: [],
				total: 0,
				total_missing_per_attribute: { ...emptyPerAttribute },
			});
		});

		render(DataHygienePage);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(1);
		});

		const chipBtns = screen.getAllByText('Author').filter(
			el => el.closest('.btn')
		);
		await fireEvent.click(chipBtns[0]);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(2);
		});

		await waitFor(() => {
			expect(screen.getByText('Your library is in great shape! All books have complete metadata for the selected attributes.')).toBeInTheDocument();
		});
	});

	it('shows empty message when filter yields no results', async () => {
		mockListMissing.mockResolvedValue({
			books: [mockBook(1)],
			total: 1,
			total_missing_per_attribute: { ...emptyPerAttribute, author: 1 },
		});

		render(DataHygienePage);

		await waitFor(() => {
			expect(screen.getByText('Book 1')).toBeInTheDocument();
		});

		mockListMissing.mockResolvedValue({
			books: [],
			total: 0,
			total_missing_per_attribute: { ...emptyPerAttribute },
		});

		const isbnBtn = Array.from(document.querySelectorAll('.btn')).find(
			btn => btn.textContent?.trim().startsWith('ISBN')
		);
		expect(isbnBtn).toBeTruthy();
		await fireEvent.click(isbnBtn!);

		await waitFor(() => {
			expect(mockListMissing).toHaveBeenCalledTimes(2);
		});

		const params = mockListMissing.mock.calls[1][0];
		expect(params.attributes).toContain('isbn');
	});
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import StatisticsPage from './+page.svelte';
import type { StatisticsResponse } from '$lib/types';

const mockStatisticsGet = vi.fn();
const mockGetPagesPerDay = vi.fn();
vi.mock('$lib/api', () => ({
	api: {
		statistics: {
			get: (...args: unknown[]) => mockStatisticsGet(...args),
			getPagesPerDay: (...args: unknown[]) => mockGetPagesPerDay(...args),
		},
	}
}));

function createMockStats(overrides?: Partial<StatisticsResponse>): StatisticsResponse {
	return {
		total_books: 3,
		total_authors: 2,
		avg_books_per_month: 1,
		busiest_month: '2026-01',
		busiest_month_count: 2,
		avg_page_count: 200,
		most_popular_language: 'EN',
		most_popular_language_count: 3,
		language_distribution: [{ language: 'EN', count: 3 }],
		status_distribution: { want_to_read: 1, currently_reading: 0, read: 2, did_not_finish: 0 },
		acquisition_status_distribution: { owned: 2, borrowed: 1, digital_access: 0, to_acquire: 1 },
		page_buckets: { pages_to_read: 100, pages_read: 200, pages_wasted: 0 },
		pages_read_per_month: [],
		books_finished_per_month: [],
		books_finished_per_year: [],
		top_authors: [],
		books_with_rating: 0,
		books_without_rating: 0,
		average_rating: null,
		top_rated_books: [],
		worst_rated_books: [],
		...overrides,
	};
}

function closestGrid(el: Element | null): Element | null {
	return el?.closest('.grid') ?? null;
}

describe('StatisticsPage', () => {
	beforeEach(() => {
		mockGetPagesPerDay.mockRejectedValue(new Error('no calendar data'));
	});

	it('renders acquisition status distribution and books by status in the same grid', async () => {
		mockStatisticsGet.mockResolvedValue(createMockStats());

		render(StatisticsPage);

		await waitFor(() => {
			expect(screen.getByText('Books by Ownership')).toBeInTheDocument();
		});

		const ownershipCard = screen.getByText('Books by Ownership').closest('.card');
		const statusCard = screen.getByText('Books by Status').closest('.card');
		expect(ownershipCard).toBeInTheDocument();
		expect(statusCard).toBeInTheDocument();
		expect(closestGrid(ownershipCard)).toBe(closestGrid(statusCard));

		expect(screen.getByText('Owned: 2')).toBeInTheDocument();
		expect(screen.getByText('Borrowed: 1')).toBeInTheDocument();
		expect(screen.getByText('Needs to be acquired: 1')).toBeInTheDocument();
		expect(screen.queryByText('Digital access: 0')).not.toBeInTheDocument();
	});

	it('renders page buckets in the same grid as acquisition distribution', async () => {
		mockStatisticsGet.mockResolvedValue(createMockStats());

		render(StatisticsPage);

		await waitFor(() => {
			expect(screen.getByText('Page Statistics')).toBeInTheDocument();
		});

		const ownershipCard = screen.getByText('Books by Ownership').closest('.card');
		const pageBucketsCard = screen.getByText('Page Statistics').closest('.card');
		expect(pageBucketsCard).toBeInTheDocument();
		expect(closestGrid(ownershipCard)).toBe(closestGrid(pageBucketsCard));

		expect(screen.getByText('Pages to Read: 100')).toBeInTheDocument();
		expect(screen.getByText('Pages Read: 200')).toBeInTheDocument();
	});

	it('shows no acquisition segments when all acquisition counts are zero', async () => {
		mockStatisticsGet.mockResolvedValue(
			createMockStats({
				status_distribution: { want_to_read: 1, currently_reading: 0, read: 0, did_not_finish: 0 },
				acquisition_status_distribution: { owned: 0, borrowed: 0, digital_access: 0, to_acquire: 0 },
			})
		);

		render(StatisticsPage);

		await waitFor(() => {
			expect(screen.getByText('Books by Ownership')).toBeInTheDocument();
		});

		expect(screen.queryByText('Owned: 0')).not.toBeInTheDocument();
	});
});

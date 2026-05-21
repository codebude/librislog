import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import CalendarCellRenderer from './CalendarCellRenderer.svelte';

const mockTooltip = { show: vi.fn(), hide: vi.fn() };

vi.mock('layerchart', async () => {
	const { default: MockRect } = await import('$lib/test/mocks/Rect.svelte');
	return {
		Rect: MockRect,
		getChartContext: vi.fn(() => ({
			tooltip: mockTooltip
		}))
	};
});

describe('CalendarCellRenderer', () => {
	const cells = [
		{ x: 0, y: 0, data: { date: '2024-01-01', pages: 10 } },
		{ x: 1, y: 0, data: { date: '2024-01-02', pages: 0 } },
		{ x: 2, y: 0, data: { date: '2024-01-03' } }
	];

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders rects for each cell', () => {
		render(CalendarCellRenderer, {
			props: { cells, cellSize: [20, 20], maxPages: 20 }
		});
		expect(document.querySelectorAll('[role="gridcell"]')).toHaveLength(3);
	});

	it('handles zero and undefined pages', () => {
		render(CalendarCellRenderer, {
			props: { cells, cellSize: [20, 20], maxPages: 20 }
		});
		const rects = document.querySelectorAll('[role="gridcell"]');
		expect(rects).toHaveLength(3);
	});

	it('uses maxPages of 1', () => {
		render(CalendarCellRenderer, {
			props: {
				cells: [{ x: 0, y: 0, data: { date: '2024-01-01', pages: 5 } }],
				cellSize: [20, 20],
				maxPages: 1
			}
		});
		expect(document.querySelector('[role="gridcell"]')).toBeInTheDocument();
	});

	it('shows tooltip on pointermove for cell with pages', async () => {
		render(CalendarCellRenderer, {
			props: { cells, cellSize: [20, 20], maxPages: 20 }
		});
		const rects = document.querySelectorAll('[role="gridcell"]');
		await fireEvent.pointerMove(rects[0]);
		expect(mockTooltip.show).toHaveBeenCalledOnce();
	});

	it('does not show tooltip on pointermove for cell without pages', async () => {
		render(CalendarCellRenderer, {
			props: { cells, cellSize: [20, 20], maxPages: 20 }
		});
		const rects = document.querySelectorAll('[role="gridcell"]');
		await fireEvent.pointerMove(rects[2]); // cell with no pages
		expect(mockTooltip.show).not.toHaveBeenCalled();
	});

	it('hides tooltip on pointerleave', async () => {
		render(CalendarCellRenderer, {
			props: { cells, cellSize: [20, 20], maxPages: 20 }
		});
		const rects = document.querySelectorAll('[role="gridcell"]');
		await fireEvent.pointerLeave(rects[0]);
		expect(mockTooltip.hide).toHaveBeenCalledOnce();
	});
});

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import StatisticsRangeSelector from './StatisticsRangeSelector.svelte';

describe('StatisticsRangeSelector', () => {
	it('renders exactly the six supported ranges', () => {
		render(StatisticsRangeSelector);
		const options = screen.getByRole('combobox').querySelectorAll('option');
		expect([...options].map((option) => option.textContent)).toEqual([
			'All time',
			'Last 3 years',
			'Last year',
			'Last 6 months',
			'Last 30 days',
			'Custom'
		]);
	});

	it('shows custom date inputs and validates their order', async () => {
		render(StatisticsRangeSelector, { props: { range: 'custom' } });
		expect(screen.getByText('From')).toBeInTheDocument();
		expect(screen.getByText('To')).toBeInTheDocument();
	});

	it('reports an invalid custom range', () => {
		render(StatisticsRangeSelector, {
			props: { range: 'custom', customFrom: '2026-03-01', customTo: '2026-02-01' }
		});
		expect(screen.getByRole('alert')).toHaveTextContent('From date cannot be after To date');
	});
});

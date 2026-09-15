import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import SearchableSelect from './SearchableSelect.svelte';

describe('SearchableSelect', () => {
	const options = ['Europe/Berlin', 'Europe/London', 'Asia/Tokyo'];

	afterEach(() => {
		cleanup();
	});

	it('renders the current value on the trigger', () => {
		render(SearchableSelect, { props: { value: 'Europe/Berlin', options, ariaLabel: 'timezone' } });
		expect(screen.getByRole('button', { name: 'timezone' })).toHaveTextContent('Europe/Berlin');
	});

	it('shows the placeholder when no value is selected', () => {
		render(SearchableSelect, {
			props: { value: '', options, placeholder: 'Pick one', ariaLabel: 'timezone' },
		});
		expect(screen.getByRole('button', { name: 'timezone' })).toHaveTextContent('Pick one');
	});

	it('opens the dropdown on click and lists all options', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.click(screen.getByRole('button', { name: 'timezone' }));
		expect(screen.getAllByRole('option')).toHaveLength(3);
		expect(screen.getByRole('combobox')).toBeInTheDocument();
	});

	it('filters options while typing', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.click(screen.getByRole('button', { name: 'timezone' }));

		const search = screen.getByRole('combobox');
		await fireEvent.input(search, { target: { value: 'Lon' } });

		const remaining = screen.getAllByRole('option');
		expect(remaining).toHaveLength(1);
		expect(remaining[0]).toHaveTextContent('Europe/London');
	});

	it('selects an option on mousedown and closes the dropdown', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.click(screen.getByRole('button', { name: 'timezone' }));

		await fireEvent.mouseDown(screen.getByText('Europe/London'));

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'timezone' })).toHaveTextContent('Europe/London');
	});

	it('closes the dropdown on Escape', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.click(screen.getByRole('button', { name: 'timezone' }));

		await fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Escape' });

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('closes the dropdown when clicking outside', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.click(screen.getByRole('button', { name: 'timezone' }));
		expect(screen.getByRole('listbox')).toBeInTheDocument();

		await fireEvent.click(document.body);

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('selects the highlighted option with ArrowDown and Enter', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.click(screen.getByRole('button', { name: 'timezone' }));

		const search = screen.getByRole('combobox');
		await fireEvent.keyDown(search, { key: 'ArrowDown' });
		await fireEvent.keyDown(search, { key: 'Enter' });

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'timezone' })).toHaveTextContent('Europe/Berlin');
	});

	it('opens the dropdown and starts filtering when a character is typed', async () => {
		render(SearchableSelect, { props: { value: '', options, ariaLabel: 'timezone' } });
		await fireEvent.keyDown(screen.getByRole('button', { name: 'timezone' }), { key: 'L' });

		expect(screen.getByRole('combobox')).toBeInTheDocument();
		expect(screen.getAllByRole('option')).toHaveLength(2);
		expect(screen.getAllByRole('option')[0]).toHaveTextContent('Europe/Berlin');
		expect(screen.getAllByRole('option')[1]).toHaveTextContent('Europe/London');
	});
});
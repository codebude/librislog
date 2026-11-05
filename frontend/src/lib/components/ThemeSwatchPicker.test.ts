import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ThemeSwatchPicker from './ThemeSwatchPicker.svelte';

const groups = [
	{ label: 'Catppuccin', themes: ['latte', 'mocha'] },
	{ label: 'DaisyUI', themes: ['dracula'] }
];

describe('ThemeSwatchPicker', () => {
	it('renders one radio per theme and checks the selected one', () => {
		render(ThemeSwatchPicker, { selected: 'latte', groups });

		expect(screen.getAllByRole('radio')).toHaveLength(3);
		expect(screen.getByRole('radio', { name: 'Latte' })).toBeChecked();
		expect(screen.getByRole('radio', { name: 'Dracula' })).not.toBeChecked();
	});

	it('marks nothing when no custom theme is active', () => {
		render(ThemeSwatchPicker, { selected: null, groups });

		expect(screen.getAllByRole('radio').some((radio) => (radio as HTMLInputElement).checked)).toBe(false);
	});

	it('names the groups so short labels keep their context', () => {
		render(ThemeSwatchPicker, { selected: 'latte', groups });

		expect(screen.getByRole('group', { name: 'Catppuccin' })).toBeInTheDocument();
		expect(screen.getByRole('group', { name: 'DaisyUI' })).toBeInTheDocument();
	});

	it('previews every theme with its own theme scope', () => {
		const { container } = render(ThemeSwatchPicker, { selected: 'latte', groups });

		for (const theme of ['latte', 'mocha', 'dracula']) {
			expect(container.querySelector(`[data-theme-option="${theme}"] [data-theme="${theme}"]`)).not.toBeNull();
		}
	});

	it('reports a newly picked theme', async () => {
		const onSelect = vi.fn();
		render(ThemeSwatchPicker, { selected: 'latte', groups, onSelect });

		await fireEvent.click(screen.getByRole('radio', { name: 'Dracula' }));

		expect(onSelect).toHaveBeenCalledWith('dracula');
	});
});

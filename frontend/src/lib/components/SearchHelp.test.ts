import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import SearchHelp from './SearchHelp.svelte';

describe('SearchHelp', () => {
	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('renders the help trigger button', () => {
		render(SearchHelp);
		expect(screen.getByRole('button', { name: 'Search syntax' })).toBeInTheDocument();
	});

	it('opens the help panel on click', async () => {
		render(SearchHelp);
		const trigger = screen.getByRole('button', { name: 'Search syntax' });

		await fireEvent.click(trigger);

		expect(screen.getByRole('dialog')).toBeInTheDocument();
		expect(screen.getByText('Use field prefixes to search in a specific field. Prefixes are always English.')).toBeInTheDocument();
	});

	it('displays the hardcoded English prefixes', async () => {
		render(SearchHelp);
		await fireEvent.click(screen.getByRole('button', { name: 'Search syntax' }));

		const dialog = screen.getByRole('dialog');
		expect(dialog).toHaveTextContent('author');
		expect(dialog).toHaveTextContent('publisher');
		expect(dialog).toHaveTextContent('title');
		expect(dialog).toHaveTextContent('tag');
		expect(dialog).toHaveTextContent('language');
		expect(dialog).toHaveTextContent('possession');
		expect(dialog).toHaveTextContent('notes');
		expect(dialog).toHaveTextContent('description');
	});

	it('displays the quoted-value and negation examples', async () => {
		render(SearchHelp);
		await fireEvent.click(screen.getByRole('button', { name: 'Search syntax' }));

		const dialog = screen.getByRole('dialog');
		expect(dialog).toHaveTextContent('author:"Christoph Dittert"');
		expect(dialog).toHaveTextContent('tag:cars -tag:audi');
	});
});
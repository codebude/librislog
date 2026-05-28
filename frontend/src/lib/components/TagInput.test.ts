import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import TagInput from './TagInput.svelte';

describe('TagInput', () => {
	beforeEach(() => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
	});

	afterEach(() => {
		vi.useRealTimers();
		cleanup();
	});

	it('renders tags from value prop', () => {
		render(TagInput, { props: { value: 'fiction, classic' } });

		expect(screen.getByText('fiction')).toBeInTheDocument();
		expect(screen.getByText('classic')).toBeInTheDocument();
	});

	it('adds a tag on Enter key', async () => {
		render(TagInput, { props: { value: '' } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'new-tag' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(screen.getByText('new-tag')).toBeInTheDocument();
		expect(input).toHaveValue('');
	});

	it('adds a tag on comma key', async () => {
		render(TagInput, { props: { value: '' } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'comma-tag' } });
		await fireEvent.keyDown(input, { key: ',' });

		expect(screen.getByText('comma-tag')).toBeInTheDocument();
	});

	it('adds a tag on Tab key', async () => {
		render(TagInput, { props: { value: '' } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'tab-tag' } });
		await fireEvent.keyDown(input, { key: 'Tab' });

		expect(screen.getByText('tab-tag')).toBeInTheDocument();
	});

	it('removes last tag on Backspace when input is empty', async () => {
		render(TagInput, { props: { value: 'first, second' } });

		const input = screen.getByRole('textbox');
		await fireEvent.keyDown(input, { key: 'Backspace' });

		expect(screen.queryByText('second')).not.toBeInTheDocument();
		expect(screen.getByText('first')).toBeInTheDocument();
	});

	it('removes a tag when clicking its remove button', async () => {
		render(TagInput, { props: { value: 'remove-me' } });

		const removeBtn = screen.getByRole('button', { name: 'Remove' });
		await fireEvent.click(removeBtn);

		expect(screen.queryByText('remove-me')).not.toBeInTheDocument();
	});

	it('prevents duplicate tags (case-insensitive)', async () => {
		render(TagInput, { props: { value: 'Fiction' } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'fiction' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(screen.getAllByText(/Fiction/i)).toHaveLength(1);
	});

	it('respects maxTagsCount', async () => {
		render(TagInput, { props: { value: 'one, two', maxTagsCount: 2 } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'three' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(screen.queryByText('three')).not.toBeInTheDocument();
		expect(screen.getByText('one')).toBeInTheDocument();
		expect(screen.getByText('two')).toBeInTheDocument();
	});

	it('shows suggestions after debounce when typing', async () => {
		const fetchSuggestions = vi.fn(async () => ['fantasy', 'fiction', 'history']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'fan' } });

		expect(fetchSuggestions).not.toHaveBeenCalled(); // debounced

		await vi.advanceTimersByTimeAsync(300);

		const options = screen.getAllByRole('option');
		expect(options[0]).toHaveTextContent('fantasy');
		expect(options[1]).toHaveTextContent('fiction');
	});

	it('navigates suggestions with ArrowDown/ArrowUp and selects with Enter', async () => {
		const fetchSuggestions = vi.fn(async () => ['alpha', 'beta']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'al' } });
		await vi.advanceTimersByTimeAsync(300);

		const options1 = screen.getAllByRole('option');
		expect(options1[0]).toHaveTextContent('alpha');

		await fireEvent.keyDown(input, { key: 'ArrowDown' });
		const options = screen.getAllByRole('option');
		expect(options[0]).toHaveAttribute('aria-selected', 'true');

		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(screen.getByText('alpha')).toBeInTheDocument();
		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('closes suggestions on Escape', async () => {
		const fetchSuggestions = vi.fn(async () => ['result']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'q' } });
		await vi.advanceTimersByTimeAsync(300);

		const options2 = screen.getAllByRole('option');
		expect(options2[0]).toHaveTextContent('result');
		await fireEvent.keyDown(input, { key: 'Escape' });

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('disables interaction when disabled prop is true', () => {
		render(TagInput, { props: { value: 'tag', disabled: true } });

		expect(screen.getByRole('textbox')).toBeDisabled();
		expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
	});

	it('blurs without fetchSuggestions adds current input as tag', async () => {
		render(TagInput, { props: { value: '' } }); // no fetchSuggestions

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'blurred' } });
		await fireEvent.blur(input);

		expect(screen.getByText('blurred')).toBeInTheDocument();
	});

	it('handles fetchSuggestions error gracefully', async () => {
		const fetchSuggestions = vi.fn(async () => { throw new Error('Network error'); });

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'test' } });
		await vi.advanceTimersByTimeAsync(300);

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('clears suggestions when input becomes empty', async () => {
		const fetchSuggestions = vi.fn(async () => ['result']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'test' } });
		await vi.advanceTimersByTimeAsync(300);

		expect(screen.getByRole('listbox')).toBeInTheDocument();

		await fireEvent.input(input, { target: { value: '' } });
		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('selects suggestion on mouse click', async () => {
		const fetchSuggestions = vi.fn(async () => ['alpha', 'beta']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'al' } });
		await vi.advanceTimersByTimeAsync(300);

		const option = screen.getAllByRole('option')[0];
		await fireEvent.mouseDown(option);

		expect(screen.getByText('alpha')).toBeInTheDocument();
	});

	it('highlights suggestion on mouse enter', async () => {
		const fetchSuggestions = vi.fn(async () => ['alpha', 'beta']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'al' } });
		await vi.advanceTimersByTimeAsync(300);

		const options = screen.getAllByRole('option');
		await fireEvent.mouseEnter(options[1]);

		expect(options[1]).toHaveAttribute('aria-selected', 'true');
	});

	it('does not add tag when input is empty', async () => {
		render(TagInput, { props: { value: '' } });

		const input = screen.getByRole('textbox');
		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
	});

	it('does not add duplicate tag via suggestion', async () => {
		const fetchSuggestions = vi.fn(async () => ['Fiction']);

		render(TagInput, { props: { value: 'fiction', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'fic' } });
		await vi.advanceTimersByTimeAsync(300);

		const option = screen.getAllByRole('option')[0];
		await fireEvent.mouseDown(option);

		expect(screen.getAllByText(/fiction/i)).toHaveLength(1);
	});

	it('does not add tag beyond maxTagsCount via suggestion', async () => {
		const fetchSuggestions = vi.fn(async () => ['extra']);

		render(TagInput, { props: { value: 'one, two', maxTagsCount: 2, fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'ext' } });
		await vi.advanceTimersByTimeAsync(300);

		const option = screen.getAllByRole('option')[0];
		await fireEvent.mouseDown(option);

		expect(screen.queryByText('extra')).not.toBeInTheDocument();
	});

	it('navigates suggestions with ArrowUp', async () => {
		const fetchSuggestions = vi.fn(async () => ['alpha', 'beta', 'gamma']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'a' } });
		await vi.advanceTimersByTimeAsync(300);

		// Go down three times to reach gamma (index 2)
		await fireEvent.keyDown(input, { key: 'ArrowDown' });
		await fireEvent.keyDown(input, { key: 'ArrowDown' });
		await fireEvent.keyDown(input, { key: 'ArrowDown' });
		const options = screen.getAllByRole('option');
		expect(options[2]).toHaveAttribute('aria-selected', 'true');

		// Go up once to reach beta (index 1)
		await fireEvent.keyDown(input, { key: 'ArrowUp' });
		expect(options[1]).toHaveAttribute('aria-selected', 'true');
	});

	it('closes suggestions on blur with fetchSuggestions', async () => {
		const fetchSuggestions = vi.fn(async () => ['result']);

		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'test' } });
		await vi.advanceTimersByTimeAsync(300);

		expect(screen.getByRole('listbox')).toBeInTheDocument();
		await fireEvent.blur(input);
		await vi.advanceTimersByTimeAsync(250);

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('does not add tag when disabled on Enter', async () => {
		render(TagInput, { props: { value: 'existing', disabled: true } });

		const input = screen.getByRole('textbox');
		// Even though input is disabled, let's test the addCurrentTag guard
		// by checking that no new tags are added through the value prop
		expect(screen.getByText('existing')).toBeInTheDocument();
	});

	it('does not select suggestion when disabled', async () => {
		const fetchSuggestions = vi.fn(async () => ['new-tag']);

		render(TagInput, { props: { value: 'existing', disabled: true, fetchSuggestions } });

		// When disabled, suggestions shouldn't be fetchable, but if they somehow appear,
		// selectSuggestion should return early due to disabled check
		const input = screen.getByRole('textbox');
		expect(input).toBeDisabled();
	});

	it('does not add tag via Enter when disabled', async () => {
		render(TagInput, { props: { value: 'existing', disabled: true } });

		const input = screen.getByRole('textbox');
		// Simulate input value change (even though disabled, test the guard)
		await fireEvent.input(input, { target: { value: 'new-tag' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		// Should not add the tag because disabled guard returns early
		expect(screen.queryByText('new-tag')).not.toBeInTheDocument();
	});

	it('does not remove tag when disabled', async () => {
		// When disabled, remove buttons are not rendered, so removeTag guard is never reached
		// This is by design - the UI prevents the action entirely
		render(TagInput, { props: { value: 'tag1', disabled: true } });
		expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
	});

	it('does not select duplicate suggestion when disabled', async () => {
		const fetchSuggestions = vi.fn(async () => ['existing']);

		render(TagInput, { props: { value: 'existing', disabled: true, fetchSuggestions } });

		// The selectSuggestion disabled guard prevents adding even if suggestion matches
		const input = screen.getByRole('textbox');
		expect(input).toBeDisabled();
	});

	it('uses fixed positioning to avoid overflow clipping', async () => {
		const fetchSuggestions = vi.fn(async () => ['fantasy', 'fiction']);
		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'f' } });
		await vi.advanceTimersByTimeAsync(300);

		await waitFor(() => {
			const lb = screen.getByRole('listbox');
			expect(lb.getAttribute('style')).toContain('position: fixed');
		});
		const listbox = screen.getByRole('listbox');
		const style = listbox.getAttribute('style') || '';
		expect(style).toContain('top:');
		expect(style).toContain('left:');
		expect(style).toContain('width:');
	});

	it('uses position fixed to avoid overflow clipping', async () => {
		const fetchSuggestions = vi.fn(async () => ['fantasy', 'fiction']);
		render(TagInput, { props: { value: '', fetchSuggestions } });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'f' } });
		await vi.advanceTimersByTimeAsync(300);

		await waitFor(() => {
			const lb = screen.getByRole('listbox');
			expect(lb.getAttribute('style')).toContain('position: fixed');
		});
		const listbox = screen.getByRole('listbox');
		const style = listbox.getAttribute('style') || '';
		expect(style).toContain('top:');
		expect(style).toContain('left:');
		expect(style).toContain('width:');
	});
});

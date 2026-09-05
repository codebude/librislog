import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import SegmentedDateInput from './SegmentedDateInput.svelte';

describe('SegmentedDateInput', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('renders three segments and a hidden field', () => {
		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_started', value: '' }
		});

		expect(container.querySelectorAll('input[data-field]')).toHaveLength(3);
		expect(container.querySelector('input[type="hidden"][name="date_started"]')).toBeInTheDocument();
	});

	it('does not jump to next segment after first digit', async () => {
		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_started', value: '' }
		});

		const segments = container.querySelectorAll<HTMLInputElement>('input[data-field]');
		const first = segments[0];

		first.focus();
		await fireEvent.input(first, { target: { value: '9' } });

		expect(document.activeElement).toBe(first);
		expect(first.value).toBe('9');
	});

	it('moves to next segment on Tab only', async () => {
		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_started', value: '' }
		});

		const segments = container.querySelectorAll<HTMLInputElement>('input[data-field]');
		const first = segments[0];
		const second = segments[1];

		first.focus();
		await fireEvent.keyDown(first, { key: 'Tab' });

		expect(document.activeElement).toBe(second);
	});

	it('accepts a full pasted date and updates hidden ISO value', async () => {
		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_finished', value: '' }
		});

		const first = container.querySelector<HTMLInputElement>('input[data-field]');
		const hidden = container.querySelector<HTMLInputElement>('input[type="hidden"][name="date_finished"]');
		expect(first).toBeTruthy();
		expect(hidden).toBeTruthy();

		const pasteEvent = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
		Object.defineProperty(pasteEvent, 'clipboardData', {
			value: {
				getData: (type: string) => (type === 'text' ? '2026-09-04' : '')
			}
		});

		await fireEvent(first!, pasteEvent);

		expect(hidden!.value).toBe('2026-09-04');
	});

	it('copies the full date on Ctrl/Cmd+C', async () => {
		const writeText = vi.fn(async () => undefined);
		Object.defineProperty(navigator, 'clipboard', {
			configurable: true,
			value: { writeText }
		});

		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_started', value: '2026-09-04' }
		});

		const first = container.querySelector<HTMLInputElement>('input[data-field]');
		expect(first).toBeTruthy();

		await fireEvent.keyDown(first!, { key: 'c', ctrlKey: true });

		expect(writeText).toHaveBeenCalledOnce();
		expect(writeText.mock.calls[0][0]).toContain('2026');
	});

	it('marks invalid on blur when date is incomplete', async () => {
		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_started', value: '' }
		});

		const day = container.querySelector<HTMLInputElement>('input[data-field="day"]');
		expect(day).toBeTruthy();

		await fireEvent.input(day!, { target: { value: '3' } });
		await fireEvent.blur(day!);

		expect(container.firstElementChild).toHaveClass('border-error');
	});

	it('marks invalid when full but impossible date is entered', async () => {
		const { container } = render(SegmentedDateInput, {
			props: { name: 'date_started', value: '' }
		});

		const day = container.querySelector<HTMLInputElement>('input[data-field="day"]');
		const month = container.querySelector<HTMLInputElement>('input[data-field="month"]');
		const year = container.querySelector<HTMLInputElement>('input[data-field="year"]');
		const hidden = container.querySelector<HTMLInputElement>('input[type="hidden"][name="date_started"]');
		expect(day).toBeTruthy();
		expect(month).toBeTruthy();
		expect(year).toBeTruthy();
		expect(hidden).toBeTruthy();

		await fireEvent.input(day!, { target: { value: '31' } });
		await fireEvent.input(month!, { target: { value: '44' } });
		await fireEvent.input(year!, { target: { value: '2026' } });

		expect(container.firstElementChild).toHaveClass('border-error');
		expect(hidden!.value).toBe('');
	});
});

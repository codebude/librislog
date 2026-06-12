import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import StarRating from './StarRating.svelte';

describe('StarRating', () => {
	it('renders 5 radio inputs', () => {
		render(StarRating, { props: { value: null } });
		expect(screen.getAllByRole('radio')).toHaveLength(5);
	});

	it('checks the star matching the value prop', () => {
		render(StarRating, { props: { value: 3 } });
		const stars = screen.getAllByRole('radio');
		expect(stars[0]).not.toBeChecked();
		expect(stars[1]).not.toBeChecked();
		expect(stars[2]).toBeChecked();
		expect(stars[3]).not.toBeChecked();
		expect(stars[4]).not.toBeChecked();
	});

	it('calls onChange with the clicked star value', async () => {
		const onChange = vi.fn();
		render(StarRating, { props: { value: null, onChange } });

		const stars = screen.getAllByRole('radio');
		await fireEvent.click(stars[3]);

		expect(onChange).toHaveBeenCalledTimes(1);
		expect(onChange).toHaveBeenCalledWith(4);
	});

	it('does not call onChange when readonly', async () => {
		const onChange = vi.fn();
		render(StarRating, { props: { value: 2, readonly: true, onChange } });

		const stars = screen.getAllByRole('radio');
		await fireEvent.click(stars[4]);

		expect(onChange).not.toHaveBeenCalled();
		expect(stars[4]).not.toBeChecked();
	});

	it('has accessible aria-labels for each star', () => {
		render(StarRating, { props: { value: null } });
		expect(screen.getByLabelText('1 star')).toBeInTheDocument();
		expect(screen.getByLabelText('5 star')).toBeInTheDocument();
	});

	it('uses fallback group name when crypto.randomUUID is unavailable', () => {
		const originalCrypto = globalThis.crypto;
		const mockCrypto = { getRandomValues: originalCrypto.getRandomValues.bind(originalCrypto) };
		Object.defineProperty(globalThis, 'crypto', {
			value: mockCrypto,
			writable: true,
			configurable: true
		});
		try {
			const { container } = render(StarRating, { props: { value: null } });
			const radios = container.querySelectorAll<HTMLInputElement>('input[type="radio"]');
			expect(radios[0].name).toMatch(/^rating-\d+$/);
			expect(radios[0].name).toBe(radios[1].name);
		} finally {
			Object.defineProperty(globalThis, 'crypto', {
				value: originalCrypto,
				writable: true,
				configurable: true
			});
		}
	});
});

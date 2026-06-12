import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import Toaster from './Toaster.svelte';

type ToastItem = { id: number; message: string; level: string };

function createStore(initial: ToastItem[]) {
	let value = initial;
	const subscribers = new Set<(next: ToastItem[]) => void>();
	return {
		subscribe(run: (next: ToastItem[]) => void) {
			run(value);
			subscribers.add(run);
			return () => subscribers.delete(run);
		},
		set(next: ToastItem[]) {
			value = next;
			subscribers.forEach((run) => run(value));
		}
	};
}

vi.mock('$lib/toasts', async () => {
	const store = createStore([]);
	return {
		toasts: {
			subscribe: store.subscribe,
			add: vi.fn(),
			remove: vi.fn(),
			__set: store.set
		}
	};
});

import { toasts } from '$lib/toasts';

describe('Toaster', () => {
	afterEach(() => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([]);
		cleanup();
		vi.clearAllMocks();
	});

	it('renders nothing when no toasts', () => {
		render(Toaster);
		expect(screen.queryByRole('alert')).not.toBeInTheDocument();
	});

	it('renders a toast message', () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([{ id: 1, message: 'Book saved', level: 'success' }]);
		render(Toaster);
		expect(screen.getByText('Book saved')).toBeInTheDocument();
	});

	it('renders multiple toasts', () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([
			{ id: 1, message: 'First toast', level: 'info' },
			{ id: 2, message: 'Second toast', level: 'warning' }
		]);
		render(Toaster);
		expect(screen.getByText('First toast')).toBeInTheDocument();
		expect(screen.getByText('Second toast')).toBeInTheDocument();
	});

	it('calls remove when dismiss button clicked', async () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([{ id: 42, message: 'Dismiss me', level: 'error' }]);
		render(Toaster);

		const dismissBtn = screen.getByRole('button', { name: 'Dismiss' });
		await fireEvent.click(dismissBtn);

		expect(toasts.remove).toHaveBeenCalledWith(42);
	});

	it('applies correct alert class for error level', () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([{ id: 1, message: 'Error!', level: 'error' }]);
		const { container } = render(Toaster);
		expect(container.querySelector('.alert-error')).toBeInTheDocument();
	});

	it('applies correct alert class for success level', () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([{ id: 1, message: 'Success!', level: 'success' }]);
		const { container } = render(Toaster);
		expect(container.querySelector('.alert-success')).toBeInTheDocument();
	});

	it('applies correct alert class for warning level', () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([{ id: 1, message: 'Warning!', level: 'warning' }]);
		const { container } = render(Toaster);
		expect(container.querySelector('.alert-warning')).toBeInTheDocument();
	});

	it('applies correct alert class for info level', () => {
		(toasts as unknown as { __set: (items: ToastItem[]) => void }).__set([{ id: 1, message: 'Info!', level: 'info' }]);
		const { container } = render(Toaster);
		expect(container.querySelector('.alert-info')).toBeInTheDocument();
	});
});

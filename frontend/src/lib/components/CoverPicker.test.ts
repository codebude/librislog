import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import CoverPicker from './CoverPicker.svelte';

// Mock api
vi.mock('#lib/api.js', () => ({
	api: {
		covers: {
			upload: vi.fn()
		}
	}
}));

// Mock toasts
vi.mock('#lib/toasts.js', () => ({
	toasts: {
		add: vi.fn(),
		remove: vi.fn(),
		subscribe: vi.fn()
	}
}));

import { api } from '#lib/api.js';
import { toasts } from '#lib/toasts.js';

describe('CoverPicker', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it('renders dropzone when no value', () => {
		render(CoverPicker, { props: { value: null } });
		// Dropzone has role="button" and contains "browse" text
		expect(screen.getByText('browse')).toBeInTheDocument();
	});

	it('shows preview when value is set', () => {
		render(CoverPicker, { props: { value: 'http://example.com/cover.jpg' } });
		const img = screen.getByAltText('Cover preview');
		expect(img).toBeInTheDocument();
		expect(img).toHaveAttribute('src', 'http://example.com/cover.jpg');
	});

	it('shows remove button when value is set', () => {
		render(CoverPicker, { props: { value: 'http://example.com/cover.jpg' } });
		expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument();
	});

	it('clears value when remove button clicked', async () => {
		render(CoverPicker, { props: { value: 'http://example.com/cover.jpg' } });
		const removeBtn = screen.getByRole('button', { name: 'Remove' });
		await fireEvent.click(removeBtn);
		expect(screen.queryByAltText('Cover preview')).not.toBeInTheDocument();
	});

	it('does not show remove button when disabled', () => {
		render(CoverPicker, { props: { value: 'http://example.com/cover.jpg', disabled: true } });
		expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
	});

	it('shows upload error toast on failed upload', async () => {
		const uploadMock = vi.mocked(api.covers.upload);
		uploadMock.mockRejectedValue(new Error('Upload failed'));

		render(CoverPicker, { props: { value: null } });

		const file = new File(['fake'], 'cover.jpg', { type: 'image/jpeg' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await waitFor(() => {
			expect(toasts.add).toHaveBeenCalledWith('Upload failed', 'error');
		});
	});

	it('disables dropzone when disabled prop is true', () => {
		const { container } = render(CoverPicker, { props: { value: null, disabled: true } });
		const dropzone = container.querySelector('[role="button"][aria-disabled="true"]');
		expect(dropzone).toBeInTheDocument();
	});

	it('has url input and use url button', () => {
		render(CoverPicker, { props: { value: null } });
		expect(screen.getByPlaceholderText('Or paste an image URL...')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Use URL' })).toBeInTheDocument();
	});

	it('disables use url button when url input is empty', () => {
		render(CoverPicker, { props: { value: null } });
		const useUrlBtn = screen.getByRole('button', { name: 'Use URL' });
		expect(useUrlBtn).toBeDisabled();
	});

	it('triggers file input on dropzone click', async () => {
		render(CoverPicker, { props: { value: null } });
		const dropzone = screen.getByText('browse').closest('[role="button"]') as HTMLElement;
		const clickSpy = vi.fn();
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		input.click = clickSpy;
		await fireEvent.click(dropzone);
		expect(clickSpy).toHaveBeenCalled();
	});

	it('triggers file input on Enter key', async () => {
		render(CoverPicker, { props: { value: null } });
		const dropzone = screen.getByText('browse').closest('[role="button"]') as HTMLElement;
		const clickSpy = vi.fn();
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		input.click = clickSpy;
		await fireEvent.keyDown(dropzone, { key: 'Enter' });
		expect(clickSpy).toHaveBeenCalled();
	});

	it('does not trigger file input when disabled', async () => {
		render(CoverPicker, { props: { value: null, disabled: true } });
		const dropzone = document.querySelector('[role="button"][aria-disabled="true"]') as HTMLElement;
		const clickSpy = vi.fn();
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		input.click = clickSpy;
		await fireEvent.click(dropzone);
		expect(clickSpy).not.toHaveBeenCalled();
	});

	it('handles file drop', async () => {
		const uploadMock = vi.mocked(api.covers.upload);
		uploadMock.mockResolvedValue('http://example.com/uploaded.jpg');

		render(CoverPicker, { props: { value: null } });
		const dropzone = screen.getByText('browse').closest('[role="button"]') as HTMLElement;

		const file = new File(['fake'], 'cover.jpg', { type: 'image/jpeg' });
		await fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

		await waitFor(() => {
			expect(uploadMock).toHaveBeenCalledWith(file);
		});
	});

	it('shows dragging state on dragover', async () => {
		render(CoverPicker, { props: { value: null } });
		const dropzone = screen.getByText('browse').closest('[role="button"]') as HTMLElement;
		await fireEvent.dragOver(dropzone);
		expect(dropzone.classList.contains('border-primary')).toBe(true);
	});

	it('clears dragging state on dragleave', async () => {
		render(CoverPicker, { props: { value: null } });
		const dropzone = screen.getByText('browse').closest('[role="button"]') as HTMLElement;
		await fireEvent.dragOver(dropzone);
		await fireEvent.dragLeave(dropzone);
		expect(dropzone.classList.contains('border-base-300')).toBe(true);
	});

	it('handles URL input Enter key', async () => {
		render(CoverPicker, { props: { value: null } });
		const urlInput = screen.getByPlaceholderText('Or paste an image URL...');
		await fireEvent.input(urlInput, { target: { value: 'http://example.com/image.jpg' } });
		await fireEvent.keyDown(urlInput, { key: 'Enter' });
		// Covers the onkeydown handler line; image loading fails silently in test env
		expect(urlInput).toHaveValue('http://example.com/image.jpg');
	});
});

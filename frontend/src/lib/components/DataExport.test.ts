import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import DataExport from './DataExport.svelte';

const mockExportData = vi.fn(async (_params: unknown) => new Blob(['test']));
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		data: {
			exportData: (params: unknown) => mockExportData(params)
		}
	}
}));

vi.mock('$lib/toasts', () => ({
	toasts: {
		add: (...args: unknown[]) => mockToastsAdd(...args),
		remove: vi.fn(),
		subscribe: vi.fn()
	}
}));

describe('DataExport', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Mock URL.createObjectURL and link.click
		global.URL.createObjectURL = vi.fn(() => 'blob:test');
		global.URL.revokeObjectURL = vi.fn();
	});

	afterEach(() => {
		cleanup();
	});

	it('renders title and description', () => {
		render(DataExport);
		expect(screen.getByRole('heading', { name: 'Export' })).toBeInTheDocument();
		expect(screen.getByText(/Choose datasets and format/)).toBeInTheDocument();
	});

	it('has all dataset checkboxes', () => {
		render(DataExport);
		expect(screen.getByLabelText('Books')).toBeInTheDocument();
		expect(screen.getByLabelText('Reading progress')).toBeInTheDocument();
		expect(screen.getByLabelText('Tags')).toBeInTheDocument();
		expect(screen.getByLabelText('Cover files')).toBeInTheDocument();
	});

	it('books checkbox is checked by default', () => {
		render(DataExport);
		expect(screen.getByLabelText('Books')).toBeChecked();
	});

	it('can toggle dataset checkboxes', async () => {
		render(DataExport);
		const booksCheckbox = screen.getByLabelText('Books');
		await fireEvent.click(booksCheckbox);
		expect(booksCheckbox).not.toBeChecked();
	});

	it('has format radio buttons', () => {
		render(DataExport);
		expect(screen.getByLabelText('JSON')).toBeInTheDocument();
		expect(screen.getByLabelText('CSV')).toBeInTheDocument();
	});

	it('JSON is selected by default', () => {
		render(DataExport);
		expect(screen.getByLabelText('JSON')).toBeChecked();
	});

	it('can change format to CSV', async () => {
		render(DataExport);
		const csvRadio = screen.getByLabelText('CSV');
		await fireEvent.click(csvRadio);
		expect(csvRadio).toBeChecked();
	});

	it('has export button', () => {
		render(DataExport);
		expect(screen.getByRole('button', { name: 'Export data' })).toBeInTheDocument();
	});

	it('disables export button when no datasets selected', async () => {
		render(DataExport);
		const booksCheckbox = screen.getByLabelText('Books');
		await fireEvent.click(booksCheckbox);
		expect(screen.getByRole('button', { name: 'Export data' })).toBeDisabled();
	});

	it('calls api.data.exportData on export', async () => {
		mockExportData.mockResolvedValue(new Blob(['test']));
		render(DataExport);

		const exportBtn = screen.getByRole('button', { name: 'Export data' });
		await fireEvent.click(exportBtn);

		await waitFor(() => {
			expect(mockExportData).toHaveBeenCalledWith(
				expect.objectContaining({
					datasets: ['books'],
					format: 'json'
				})
			);
		});
	});

	it('shows success toast after export', async () => {
		mockExportData.mockResolvedValue(new Blob(['test']));
		render(DataExport);

		const exportBtn = screen.getByRole('button', { name: 'Export data' });
		await fireEvent.click(exportBtn);

		await waitFor(() => {
			expect(mockToastsAdd).toHaveBeenCalledWith('Export ready. Download started.', 'success');
		});
	});

	it('shows error toast on export failure', async () => {
		mockExportData.mockRejectedValue(new Error('Export failed'));
		render(DataExport);

		const exportBtn = screen.getByRole('button', { name: 'Export data' });
		await fireEvent.click(exportBtn);

		await waitFor(() => {
			expect(mockToastsAdd).toHaveBeenCalledWith('Export failed', 'error');
		});
	});

	it('shows progress bar while exporting', async () => {
		mockExportData.mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 100)));
		render(DataExport);

		const exportBtn = screen.getByRole('button', { name: 'Export data' });
		await fireEvent.click(exportBtn);

		expect(document.querySelector('progress')).toBeInTheDocument();
	});

	it('toggles multiple datasets', async () => {
		render(DataExport);
		const booksCheckbox = screen.getByLabelText('Books');
		const tagsCheckbox = screen.getByLabelText('Tags');

		await fireEvent.click(tagsCheckbox);
		expect(tagsCheckbox).toBeChecked();

		await fireEvent.click(booksCheckbox);
		expect(booksCheckbox).not.toBeChecked();
	});

	it('calls export with multiple datasets', async () => {
		mockExportData.mockResolvedValue(new Blob(['test']));
		render(DataExport);

		const tagsCheckbox = screen.getByLabelText('Tags');
		await fireEvent.click(tagsCheckbox);

		const exportBtn = screen.getByRole('button', { name: 'Export data' });
		await fireEvent.click(exportBtn);

		await waitFor(() => {
			expect(mockExportData).toHaveBeenCalledWith(
				expect.objectContaining({
					datasets: ['books', 'tags']
				})
			);
		});
	});

	it('shows error toast when no datasets selected', async () => {
		render(DataExport);

		// Uncheck the default "books" checkbox
		const booksCheckbox = screen.getByLabelText('Books');
		await fireEvent.click(booksCheckbox);

		// The export button is disabled when no datasets are selected,
		// so we dispatch a click event directly on the button element
		const exportBtn = screen.getByRole('button', { name: 'Export data' });
		exportBtn.removeAttribute('disabled');
		await fireEvent.click(exportBtn);

		expect(mockToastsAdd).toHaveBeenCalledWith('Select at least one dataset.', 'error');
		expect(mockExportData).not.toHaveBeenCalled();
	});
});

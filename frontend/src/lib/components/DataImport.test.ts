import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import DataImport from './DataImport.svelte';

const mockParseImportFile = vi.fn(async (_file: File) => ({
	file_id: 'test-file-123',
	format: 'csv' as const,
	source_fields: ['Book Title', 'Author Name', 'ISBN'],
	sample_rows: [{ 'Book Title': 'Dune', 'Author Name': 'Frank Herbert', 'ISBN': '978-3-16-148410-0' }],
	row_count: 1
}));
const mockSuggestMapping = vi.fn(async (_fileId: string) => ({
	suggested_mapping: { title: 'Book Title', author: 'Author Name', isbn: 'ISBN' },
	db_fields: ['title', 'author', 'isbn', 'publisher', 'page_count']
}));
const mockValidateImport = vi.fn(async (_params: unknown) => ({
	valid: true,
	row_count: 1,
	warnings: [],
	errors: []
}));
const mockListMappings = vi.fn(async () => []);
const mockExecuteImport = vi.fn(async function* (_params: unknown) {
	yield { event: 'start', total_rows: 1 };
	yield { event: 'progress', processed: 1, total: 1, percent: 100 };
	yield { event: 'complete', imported: 1, failed: 0, failures: [] };
});
const mockToastsAdd = vi.fn();

vi.mock('$lib/api', () => ({
	api: {
		data: {
			parseImportFile: (file: File) => mockParseImportFile(file),
			suggestMapping: (fileId: string) => mockSuggestMapping(fileId),
			validateImport: (params: unknown) => mockValidateImport(params),
			executeImport: (params: unknown) => mockExecuteImport(params),
			listMappings: () => mockListMappings(),
			saveMapping: vi.fn(),
			getMapping: vi.fn(),
			deleteMapping: vi.fn()
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

describe('DataImport', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it('renders title and description', () => {
		render(DataImport);
		expect(screen.getByRole('heading', { name: 'Import' })).toBeInTheDocument();
		expect(screen.getByText(/Upload one CSV or JSON file/)).toBeInTheDocument();
	});

	it('has dropzone for file upload', () => {
		render(DataImport);
		expect(screen.getByText('browse')).toBeInTheDocument();
	});

	it('has parse button', () => {
		render(DataImport);
		expect(screen.getByRole('button', { name: 'Parse file' })).toBeInTheDocument();
	});

	it('disables parse button when no file selected', () => {
		render(DataImport);
		expect(screen.getByRole('button', { name: 'Parse file' })).toBeDisabled();
	});

	it('shows file name after selection', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });
		expect(screen.getByText('books.csv')).toBeInTheDocument();
	});

	it('enables parse button after file selection', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });
		expect(screen.getByRole('button', { name: 'Parse file' })).not.toBeDisabled();
	});

	it('calls parse API when parse button clicked', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		const parseBtn = screen.getByRole('button', { name: 'Parse file' });
		await fireEvent.click(parseBtn);

		await waitFor(() => {
			expect(mockParseImportFile).toHaveBeenCalled();
		});
	});

	it('shows file summary after parsing', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Parse file' }));

		await waitFor(() => {
			expect(screen.getByText(/Rows: 1, fields: 3/)).toBeInTheDocument();
		});
	});

	it('shows mapping section after parsing', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Parse file' }));

		await waitFor(() => {
			expect(screen.getByText('Field mapping')).toBeInTheDocument();
		});
	});

	it('has simulate button', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });
		await fireEvent.click(screen.getByRole('button', { name: 'Parse file' }));

		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Simulate' })).toBeInTheDocument();
		});
	});

	it('has import mode dropdown', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });
		await fireEvent.click(screen.getByRole('button', { name: 'Parse file' }));

		await waitFor(() => {
			expect(screen.getByText('Rollback all on error')).toBeInTheDocument();
		});
	});

	it('has create progress checkbox', async () => {
		render(DataImport);
		const file = new File(['test'], 'books.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });
		await fireEvent.click(screen.getByRole('button', { name: 'Parse file' }));

		await waitFor(() => {
			expect(screen.getByLabelText('Create 100% progress entry for books imported as \'Read\'')).toBeInTheDocument();
		});
	});
});

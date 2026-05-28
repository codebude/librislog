import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ImportMappingEditor from './ImportMappingEditor.svelte';

describe('ImportMappingEditor', () => {
	const onChange = vi.fn();
	const sourceFields = ['Author', 'Title', 'ISBN'];
	const dbFields = ['author', 'title', 'isbn', 'publisher', 'page_count'];

	beforeEach(() => {
		onChange.mockClear();
	});

	it('renders all db target fields', () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		expect(screen.getByText('author')).toBeInTheDocument();
		expect(screen.getByText('title')).toBeInTheDocument();
		expect(screen.getByText('isbn')).toBeInTheDocument();
		expect(screen.getByText('publisher')).toBeInTheDocument();
		expect(screen.getByText('page_count')).toBeInTheDocument();
	});

	it('marks mandatory fields with asterisk', () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		const mandatory = screen.getAllByText('*');
		expect(mandatory.length).toBeGreaterThanOrEqual(3); // title, author, page_count (+ legend)
	});

	it('renders a select for each db field with none option', () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		const selects = screen.getAllByRole('combobox');
		expect(selects).toHaveLength(5); // one per db field
		selects.forEach((select) => {
			expect(select).toHaveValue('');
		});
	});

	it('shows existing mapping values', () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: {
					author: { source: 'Author', transform: null },
					title: { source: 'Title', transform: null }
				},
				onChange
			}
		});
		// author row should show "Author" selected
		const authorSelect = screen.getByRole('combobox', { name: /Map source for author/i });
		expect(authorSelect).toHaveValue('Author');
		// title row should show "Title" selected
		const titleSelect = screen.getByRole('combobox', { name: /Map source for title/i });
		expect(titleSelect).toHaveValue('Title');
		// isbn row should show empty
		const isbnSelect = screen.getByRole('combobox', { name: /Map source for isbn/i });
		expect(isbnSelect).toHaveValue('');
	});

	it('calls onChange when mapping is created', async () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		const authorSelect = screen.getByRole('combobox', { name: /Map source for author/i });
		await fireEvent.change(authorSelect, { target: { value: 'Author' } });
		expect(onChange).toHaveBeenCalledWith({ author: { source: 'Author', transform: null } });
	});

	it('calls onChange when mapping is cleared', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { author: { source: 'Author', transform: null } },
				onChange
			}
		});
		const authorSelect = screen.getByRole('combobox', { name: /Map source for author/i });
		await fireEvent.change(authorSelect, { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ author: { source: '', transform: null } });
	});

	it('allows same source field mapped to multiple targets', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { author: { source: 'Author', transform: null } },
				onChange
			}
		});
		const titleSelect = screen.getByRole('combobox', { name: /Map source for title/i });
		await fireEvent.change(titleSelect, { target: { value: 'Author' } });
		// Author should now map to both title and author
		expect(onChange).toHaveBeenCalledWith({
			title: { source: 'Author', transform: null },
			author: { source: 'Author', transform: null }
		});
	});

	it('shows transform textarea after clicking expand', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { author: { source: 'Author', transform: null } },
				onChange
			}
		});
		await fireEvent.click(screen.getByText('Transform (Python)'));
		expect(screen.getByLabelText(/Transform for author/i)).toBeInTheDocument();
	});

	it('calls onChange with transform when typing in transform textarea', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { author: { source: 'Author', transform: null } },
				onChange
			}
		});
		await fireEvent.click(screen.getByText('Transform (Python)'));
		const textarea = screen.getByLabelText(/Transform for author/i);
		await fireEvent.input(textarea, { target: { value: 'value.upper()' } });
		expect(onChange).toHaveBeenCalledWith({ author: { source: 'Author', transform: 'value.upper()' } });
	});

	it('clears transform via onChange when source is cleared', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { author: { source: 'Author', transform: 'value.upper()' } },
				onChange
			}
		});
		const authorSelect = screen.getByRole('combobox', { name: /Map source for author/i });
		await fireEvent.change(authorSelect, { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({ author: { source: '', transform: null } });
	});
});

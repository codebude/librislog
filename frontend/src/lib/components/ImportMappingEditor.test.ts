import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ImportMappingEditor from './ImportMappingEditor.svelte';

describe('ImportMappingEditor', () => {
	const onChange = vi.fn();
	const sourceFields = ['Author', 'Title', 'ISBN'];
	const dbFields = ['author', 'title', 'isbn', 'publisher'];

	it('renders all source fields', () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		expect(screen.getByText('Author')).toBeInTheDocument();
		expect(screen.getByText('Title')).toBeInTheDocument();
		expect(screen.getByText('ISBN')).toBeInTheDocument();
	});

	it('renders skip option for each source field', () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		const selects = screen.getAllByRole('combobox');
		expect(selects).toHaveLength(3);
		selects.forEach((select) => {
			expect(select).toHaveValue('');
		});
	});

	it('shows existing mapping values', () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { Author: 'author', Title: 'title' },
				onChange
			}
		});
		const selects = screen.getAllByRole('combobox');
		expect(selects[0]).toHaveValue('author');
		expect(selects[1]).toHaveValue('title');
		expect(selects[2]).toHaveValue('');
	});

	it('calls onChange when mapping is updated', async () => {
		render(ImportMappingEditor, {
			props: { sourceFields, dbFields, mapping: {}, onChange }
		});
		const selects = screen.getAllByRole('combobox');
		await fireEvent.change(selects[0], { target: { value: 'author' } });
		expect(onChange).toHaveBeenCalledWith({ Author: 'author' });
	});

	it('calls onChange when mapping is cleared', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { Author: 'author' },
				onChange
			}
		});
		const selects = screen.getAllByRole('combobox');
		await fireEvent.change(selects[0], { target: { value: '' } });
		expect(onChange).toHaveBeenCalledWith({});
	});

	it('calls onChange when mapping is changed', async () => {
		render(ImportMappingEditor, {
			props: {
				sourceFields,
				dbFields,
				mapping: { Author: 'author' },
				onChange
			}
		});
		const selects = screen.getAllByRole('combobox');
		await fireEvent.change(selects[0], { target: { value: 'title' } });
		expect(onChange).toHaveBeenCalledWith({ Author: 'title' });
	});
});

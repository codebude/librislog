import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import CoverCandidateGrid from './CoverCandidateGrid.svelte';
import type { CoverCandidate } from '$lib/types';

const candidates: CoverCandidate[] = [
	{ source: 'abebooks', url: 'https://example.com/1.jpg', available: true, filesize: 20408, width: 200, height: 300, content_type: 'image/jpeg' },
	{ source: 'hardcover', url: 'https://example.com/2.jpg', available: true, filesize: 3706413, width: 500, height: 800, content_type: 'image/jpeg' },
	{ source: 'amazon', url: 'https://example.com/3.jpg', available: false, filesize: null, width: null, height: null, content_type: null },
	{ source: 'thalia', url: 'https://example.com/4.jpg', available: false, filesize: 12036, width: null, height: null, content_type: null }
];

describe('CoverCandidateGrid', () => {
	it('renders loading spinner', () => {
		render(CoverCandidateGrid, { props: { loading: true, candidates: [], onSelect: vi.fn() } });
		expect(screen.getByText('Searching cover sources...')).toBeInTheDocument();
	});

	it('renders candidates sorted by resolution descending', () => {
		render(CoverCandidateGrid, { props: { loading: false, candidates, onSelect: vi.fn() } });
		const buttons = screen.getAllByRole('button').filter(b => b.querySelector('img'));
		expect(buttons).toHaveLength(2);
	});

	it('calls onSelect when candidate clicked', async () => {
		const onSelect = vi.fn();
		render(CoverCandidateGrid, { props: { loading: false, candidates, onSelect } });
		const buttons = screen.getAllByRole('button').filter(b => b.querySelector('img'));
		await fireEvent.click(buttons[0]);
		expect(onSelect).toHaveBeenCalledTimes(1);
		expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ source: 'hardcover' }));
	});

	it('shows empty message when no available candidates', () => {
		const empty = candidates.filter(c => c.available === false);
		render(CoverCandidateGrid, { props: { loading: false, candidates: empty, onSelect: vi.fn() } });
		expect(screen.getByText('No cover candidates were found for this ISBN.')).toBeInTheDocument();
	});

	it('shows custom empty message when provided', () => {
		render(CoverCandidateGrid, {
			props: { loading: false, candidates: [], onSelect: vi.fn(), emptyMessage: 'Custom empty message' }
		});
		expect(screen.getByText('Custom empty message')).toBeInTheDocument();
	});

	it('shows error alert', () => {
		render(CoverCandidateGrid, {
			props: { loading: false, candidates: [], error: 'Something went wrong', onSelect: vi.fn() }
		});
		expect(screen.getByText('Something went wrong')).toBeInTheDocument();
	});

	it('disables interaction when disabled prop is true', () => {
		const onSelect = vi.fn();
		render(CoverCandidateGrid, {
			props: { loading: false, candidates, onSelect, disabled: true }
		});
		const buttons = screen.getAllByRole('button').filter(b => b.querySelector('img'));
		buttons.forEach(b => expect(b).toBeDisabled());
	});

	it('shows filesize and resolution labels', () => {
		render(CoverCandidateGrid, { props: { loading: false, candidates, onSelect: vi.fn() } });
		expect(document.body.textContent).toContain('19.9 KB');
		expect(document.body.textContent).toContain('3.5 MB');
		expect(document.body.textContent).toContain('200x300');
		expect(document.body.textContent).toContain('500x800');
	});

	it('shows n/a for missing filesize and resolution when unloaded', () => {
		const missing: CoverCandidate[] = [
			{ source: 'amazon', url: 'https://example.com/x.jpg', available: true, filesize: null, width: null, height: null, content_type: null }
		];
		render(CoverCandidateGrid, { props: { loading: false, candidates: missing, onSelect: vi.fn() } });
		expect(document.body.textContent).toContain('n/a');
	});

	it('updates resolution from image onload event', async () => {
		const single: CoverCandidate[] = [
			{ source: 'abebooks', url: 'https://example.com/load.jpg', available: true, filesize: 1000, width: null, height: null, content_type: null }
		];
		render(CoverCandidateGrid, { props: { loading: false, candidates: single, onSelect: vi.fn() } });
		const img = document.querySelector('img');
		expect(img).toBeTruthy();
		const loadEvent = new Event('load');
		Object.defineProperty(img!, 'naturalWidth', { value: 800 });
		Object.defineProperty(img!, 'naturalHeight', { value: 1200 });
		await fireEvent(img!, loadEvent);
		expect(document.body.textContent).toContain('800x1200');
	});
});

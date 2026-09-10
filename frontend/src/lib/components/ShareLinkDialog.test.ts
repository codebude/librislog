import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { readable } from 'svelte/store';
import ShareLinkDialog from './ShareLinkDialog.svelte';
import { defaultPublicProfileVisibilityConfig } from '$lib/publicProfile/sections';
import type { PublicProfileLink } from '$lib/types';

vi.mock('$lib/i18n', () => {
	const t = (key: string) => `[${key}]`;
	return { _: readable(t) };
});

function createLink(overrides?: Partial<PublicProfileLink>): PublicProfileLink {
	const visibility_config = defaultPublicProfileVisibilityConfig();
	return {
		id: 1,
		name: 'Friends & family',
		token_prefix: 'lp_9f2c81a4e7d3',
		audience: 'public',
		visibility_config,
		expires_at: null,
		created_at: '2026-01-01T00:00:00Z',
		...overrides
	};
}

describe('ShareLinkDialog', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it('renders a create dialog with defaults and disables save until a name is entered', async () => {
		const onSave = vi.fn();
		const onClose = vi.fn();
		const { container, unmount } = render(ShareLinkDialog, {
			props: { open: true, link: null, onSave, onClose }
		});

		const dialog = container.querySelector('dialog');
		expect(dialog).toBeTruthy();
		expect(dialog!.getAttribute('aria-modal')).toBe('true');

		const nameInput = container.querySelector<HTMLInputElement>('input[name="share-link-name"]')!;
		expect(nameInput).toBeTruthy();
		const submit = container.querySelector<HTMLButtonElement>('button[type="submit"]')!;
		expect(submit.disabled).toBe(true);

		await fireEvent.input(nameInput, { target: { value: 'My profile' } });
		expect(submit.disabled).toBe(false);

		const checkedSections = [...container.querySelectorAll<HTMLInputElement>('input[name="share-link-section"]:checked')].map(
			(i) => i.value
		);
		expect(checkedSections).toEqual(defaultPublicProfileVisibilityConfig().sections);

		await fireEvent.click(submit);
		expect(onSave).toHaveBeenCalledTimes(1);
		const payload = onSave.mock.calls[0][0] as {
			name: string;
			audience: string;
			expires_at: string | null;
			visibility_config: { sections: string[]; statistics: string[] };
		};
		expect(payload.name).toBe('My profile');
		expect(payload.audience).toBe('public');
		expect(payload.visibility_config.sections).toEqual(defaultPublicProfileVisibilityConfig().sections);
		expect(payload.visibility_config.statistics).toEqual(defaultPublicProfileVisibilityConfig().statistics);
		expect(payload.expires_at).toBeNull();
		unmount();
	});

	it('prefills an existing link and unchecking statistics clears selected statistics', async () => {
		const link = createLink({
			name: 'Friends',
			audience: 'authenticated',
			visibility_config: {
				sections: ['username', 'user_info', 'currently_reading', 'statistics'],
				statistics: ['total_books', 'total_authors']
			},
			expires_at: '2026-12-31T12:00:00Z'
		});
		const onSave = vi.fn();
		const onClose = vi.fn();
		const { container, unmount } = render(ShareLinkDialog, {
			props: { open: true, link, onSave, onClose }
		});

		const nameInput = container.querySelector<HTMLInputElement>('input[name="share-link-name"]')!;
		expect(nameInput.value).toBe('Friends');
		const authRadio = container.querySelector<HTMLInputElement>('input[name="share-link-audience"][value="authenticated"]')!;
		expect(authRadio.checked).toBe(true);

		const statisticsCheckbox = [...container.querySelectorAll<HTMLInputElement>('input[name="share-link-section"]')].find(
			(i) => i.value === 'statistics'
		)!;
		await fireEvent.click(statisticsCheckbox);
		const statsCheckboxes = [...container.querySelectorAll<HTMLInputElement>('input[name="share-link-statistic"]')];
		expect(statsCheckboxes.every((c) => !c.checked)).toBe(true);

		await fireEvent.click(container.querySelector<HTMLButtonElement>('button[type="submit"]')!);
		const payload = onSave.mock.calls[0][0] as {
			visibility_config: { sections: string[]; statistics: string[] };
			expires_at: string | null;
			audience: string;
		};
		expect(payload.visibility_config.statistics).toEqual([]);
		expect(payload.visibility_config.sections).not.toContain('statistics');
		expect(payload.expires_at).toBe(new Date('2026-12-31T23:59:59').toISOString());
		unmount();
	});

	it('closes on Escape', async () => {
		const onSave = vi.fn();
		const onClose = vi.fn();
		const { container, unmount } = render(ShareLinkDialog, {
			props: { open: true, link: null, onSave, onClose }
		});

		const dialog = container.querySelector('dialog')!;
		await fireEvent.keyDown(dialog, { key: 'Escape' });
		expect(onClose).toHaveBeenCalledTimes(1);
		unmount();
	});

	it('does not render anything when closed', () => {
		const { container } = render(ShareLinkDialog, {
			props: { open: false, link: null, onSave: vi.fn(), onClose: vi.fn() }
		});
		expect(container.querySelector('dialog')).toBeNull();
	});
});
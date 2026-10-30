import { describe, it, expect, afterEach } from 'vitest';
import { render, fireEvent, cleanup } from '@testing-library/svelte';
import UserAvatar from './UserAvatar.svelte';

describe('UserAvatar', () => {
	afterEach(() => cleanup());

	it('renders an image when an avatar URL is available', () => {
		const { container } = render(UserAvatar, {
			props: { avatarUrl: '/api/users/1/avatar?v=1', seed: 'user@example.com' }
		});
		const image = container.querySelector('img');
		expect(image).toBeTruthy();
		expect(image!.getAttribute('src')).toBe('/api/users/1/avatar?v=1');
		expect(image!.getAttribute('referrerpolicy')).toBe('no-referrer');
	});

	it('falls back to the animal avatar when the image fails to load', async () => {
		const { container } = render(UserAvatar, {
			props: { avatarUrl: '/api/users/1/avatar?v=1', seed: 'user@example.com' }
		});
		const image = container.querySelector('img');
		expect(image).toBeTruthy();
		await fireEvent.error(image!);
		expect(container.querySelector('img')).toBeNull();
	});

	it('renders the animal avatar when no URL is provided', () => {
		const { container } = render(UserAvatar, {
			props: { avatarUrl: null, seed: 'user@example.com' }
		});
		expect(container.querySelector('img')).toBeNull();
		expect(container.querySelector('svg')).toBeTruthy();
	});
});

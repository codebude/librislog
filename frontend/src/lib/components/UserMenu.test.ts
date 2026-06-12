import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import UserMenu from './UserMenu.svelte';

const mockGoto = vi.fn();
const mockLogout = vi.fn(async () => {});
const mockBroadcastLogout = vi.fn();

// Create stores inside mock factory to avoid hoisting issues
vi.mock('$lib/stores/auth', async () => {
	const { writable } = await import('svelte/store');
	return {
		currentUser: writable<{ id: number; firstname: string; lastname: string; email: string; role: 'admin' | 'user'; created_at: string } | null>(null),
		csrfToken: writable<string | null>(null),
		broadcastLogout: () => mockBroadcastLogout()
	};
});

vi.mock('$app/navigation', () => ({
	goto: (path: string) => mockGoto(path)
}));

vi.mock('$lib/api', () => ({
	api: {
		auth: {
			logout: () => mockLogout()
		}
	}
}));

import { currentUser, csrfToken } from '$lib/stores/auth';

describe('UserMenu', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		currentUser.set(null);
		csrfToken.set(null);
	});

	afterEach(() => {
		cleanup();
	});

	const mockUser = {
		id: 1,
		firstname: 'John',
		lastname: 'Doe',
		email: 'john@example.com',
		role: 'user' as const,
		created_at: '2024-01-01T00:00:00Z'
	};

	it('renders user avatar button', () => {
		currentUser.set(mockUser);
		render(UserMenu);
		expect(screen.getByRole('button', { name: 'User menu' })).toBeInTheDocument();
	});

	it('shows user avatar', () => {
		currentUser.set(mockUser);
		render(UserMenu);
		expect(screen.getByRole('button', { name: 'User menu' }).querySelector('svg')).toBeInTheDocument();
	});

	it('shows ?? when no user', () => {
		currentUser.set(null);
		render(UserMenu);
		expect(screen.getByText('??')).toBeInTheDocument();
	});

	it('opens dropdown when clicked', async () => {
		currentUser.set(mockUser);
		render(UserMenu);

		const menuBtn = screen.getByRole('button', { name: 'User menu' });
		await fireEvent.click(menuBtn);

		expect(screen.getByRole('link', { name: 'Profile' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
	});

	it('has profile link', async () => {
		currentUser.set(mockUser);
		render(UserMenu);

		await fireEvent.click(screen.getByRole('button', { name: 'User menu' }));
		const profileLink = screen.getByRole('link', { name: 'Profile' });
		expect(profileLink).toHaveAttribute('href', '/profile');
	});

	it('calls logout API and redirects on logout', async () => {
		currentUser.set(mockUser);
		csrfToken.set('test-csrf');
		render(UserMenu);

		await fireEvent.click(screen.getByRole('button', { name: 'User menu' }));
		const logoutBtn = screen.getByRole('button', { name: 'Logout' });
		await fireEvent.click(logoutBtn);

		expect(mockLogout).toHaveBeenCalled();
		expect(mockBroadcastLogout).toHaveBeenCalled();
		expect(mockGoto).toHaveBeenCalledWith('/login');
	});

	it('clears stores on logout', async () => {
		currentUser.set(mockUser);
		csrfToken.set('test-csrf');
		render(UserMenu);

		await fireEvent.click(screen.getByRole('button', { name: 'User menu' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

		let userValue: unknown;
		currentUser.subscribe((v) => { userValue = v; })();
		expect(userValue).toBeNull();

		let csrfValue: unknown;
		csrfToken.subscribe((v) => { csrfValue = v; })();
		expect(csrfValue).toBeNull();
	});

	it('handles logout API failure gracefully', async () => {
		mockLogout.mockRejectedValue(new Error('Network error'));
		currentUser.set(mockUser);
		render(UserMenu);

		await fireEvent.click(screen.getByRole('button', { name: 'User menu' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

		expect(mockGoto).toHaveBeenCalledWith('/login');
	});

	it('closes dropdown when logout clicked', async () => {
		currentUser.set(mockUser);
		render(UserMenu);

		await fireEvent.click(screen.getByRole('button', { name: 'User menu' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

		expect(screen.queryByRole('link', { name: 'Profile' })).not.toBeInTheDocument();
	});

	it('closes dropdown when profile link clicked', async () => {
		currentUser.set(mockUser);
		render(UserMenu);

		await fireEvent.click(screen.getByRole('button', { name: 'User menu' }));
		await fireEvent.click(screen.getByRole('link', { name: 'Profile' }));

		expect(screen.queryByRole('link', { name: 'Profile' })).not.toBeInTheDocument();
	});
});

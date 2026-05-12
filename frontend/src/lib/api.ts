import type {
	ApiKeyMeta,
	Book,
	BookImportCandidate,
	DashboardQuote,
	LibraryStats,
	StatusTransitionRequest,
	StatusTransitionResponse,
	ImportSearchMode,
	ReadingStatus,
	SearchStage,
	SortField,
	SortOrder,
	OidcConfig,
	OidcLinkStatus,
	User,
	UserAdminUpdate,
	UserSettings
} from './types';
import { apiKey } from './stores/auth';
import { get } from 'svelte/store';

const BASE = '/api';

function authHeaders(): Record<string, string> {
	const key = get(apiKey);
	return key ? { 'X-API-Key': key } : {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...authHeaders()
	};
	if (options?.headers) {
		Object.assign(headers, options.headers as Record<string, string>);
	}

	const res = await fetch(`${BASE}${path}`, {
		headers,
		...options
	});

	const contentType = res.headers.get('content-type') ?? '';
	const isJson = contentType.includes('application/json');

	if (!res.ok) {
		if (isJson) {
			const detail = await res.json().catch(() => ({}));
			throw new Error(detail?.detail ?? `HTTP ${res.status}`);
		}
		const text = await res.text().catch(() => '');
		throw new Error(text || `HTTP ${res.status}`);
	}
	if (res.status === 204) return undefined as T;
	if (!isJson) {
		throw new Error(`Unexpected non-JSON response for ${path}`);
	}
	return res.json() as Promise<T>;
}

export const api = {
	auth: {
		setupRequired(): Promise<{ required: boolean }> {
			return request<{ required: boolean }>('/auth/setup-required');
		},

		setup(data: {
			firstname: string;
			lastname: string;
			email: string;
			password: string;
		}): Promise<{ user: User; api_key: string }> {
			return request<{ user: User; api_key: string }>('/auth/setup', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		login(data: { email: string; password: string }): Promise<{ user: User; api_key: string }> {
			return request<{ user: User; api_key: string }>('/auth/login', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		me(): Promise<User> {
			return request<User>('/auth/me');
		},

		logout(): Promise<{ message: string }> {
			return request<{ message: string }>('/auth/logout', { method: 'POST' });
		}
	},

	profile: {
		get(): Promise<User> {
			return request<User>('/profile');
		},

		update(data: Partial<Pick<User, 'firstname' | 'lastname'>> & { password?: string }): Promise<User> {
			return request<User>('/profile', { method: 'PATCH', body: JSON.stringify(data) });
		},

		getSettings(): Promise<UserSettings> {
			return request<UserSettings>('/profile/settings');
		},

		updateSettings(data: { language?: string }): Promise<UserSettings> {
			return request<UserSettings>('/profile/settings', {
				method: 'PATCH',
				body: JSON.stringify(data)
			});
		},

		listApiKeys(): Promise<ApiKeyMeta[]> {
			return request<ApiKeyMeta[]>('/profile/api-keys');
		},

		createApiKey(data: { description?: string | null }): Promise<{ key: string; api_key: ApiKeyMeta }> {
			return request<{ key: string; api_key: ApiKeyMeta }>('/profile/api-keys', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		deleteApiKey(id: number): Promise<void> {
			return request<void>(`/profile/api-keys/${id}`, { method: 'DELETE' });
		}
	},

	users: {
		list(): Promise<User[]> {
			return request<User[]>('/users');
		},

		create(data: {
			firstname: string;
			lastname: string;
			email: string;
			password: string;
			role: 'admin' | 'user';
		}): Promise<{ user: User; api_key: string }> {
			return request<{ user: User; api_key: string }>('/users', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		update(id: number, data: UserAdminUpdate): Promise<User> {
			return request<User>(`/users/${id}`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			});
		},

		delete(id: number): Promise<void> {
			return request<void>(`/users/${id}`, { method: 'DELETE' });
		}
	},

		oidc: {
		config(): Promise<OidcConfig> {
			return request<OidcConfig>('/oidc/config');
		},

		loginUrl(): string {
			return `${BASE}/oidc/login`;
		},

		linkStatus(): Promise<OidcLinkStatus> {
			return request<OidcLinkStatus>('/oidc/link-status');
		},

		startLink(): Promise<{ redirect_url: string }> {
			return request<{ redirect_url: string }>('/oidc/link', { method: 'POST' });
		},

		unlink(): Promise<void> {
			return request<void>('/oidc/unlink', { method: 'DELETE' });
		}
	},

	books: {
		stats(): Promise<LibraryStats> {
			return request<LibraryStats>('/books/stats');
		},

		dashboardQuote(): Promise<DashboardQuote | null> {
			return request<DashboardQuote | null>('/books/dashboard-quote');
		},

		list(params?: {
			status?: ReadingStatus;
			q?: string;
			sort?: SortField;
			order?: SortOrder;
			smart_sort?: boolean;
		}): Promise<Book[]> {
			const qs = new URLSearchParams();
			if (params?.status) qs.set('status', params.status);
			if (params?.q) qs.set('q', params.q);
			if (params?.sort) qs.set('sort', params.sort);
			if (params?.order) qs.set('order', params.order);
			if (params?.smart_sort !== undefined) qs.set('smart_sort', String(params.smart_sort));
			const query = qs.toString() ? `?${qs}` : '';
			return request<Book[]>(`/books${query}`);
		},

		get(id: number): Promise<Book> {
			return request<Book>(`/books/${id}`);
		},

		create(data: Partial<Book>): Promise<Book> {
			return request<Book>('/books', { method: 'POST', body: JSON.stringify(data) });
		},

		update(id: number, data: Partial<Book>): Promise<Book> {
			return request<Book>(`/books/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
		},

		transitionStatus(id: number, data: StatusTransitionRequest): Promise<StatusTransitionResponse> {
			return request<StatusTransitionResponse>(`/books/${id}/transition-status`, {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		delete(id: number): Promise<void> {
			return request<void>(`/books/${id}`, { method: 'DELETE' });
		}
	},

	covers: {
		async upload(file: File): Promise<string> {
			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${BASE}/covers/upload`, {
				method: 'POST',
				headers: authHeaders(),
				body: form
			});
			if (!res.ok) {
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			const data = (await res.json()) as { cover_url: string };
			return data.cover_url;
		}
	},

	import: {
		search(q: string, type: 'title' | 'isbn' = 'title'): Promise<BookImportCandidate[]> {
			return request<BookImportCandidate[]>(
				`/import/search?q=${encodeURIComponent(q)}&type=${type}`
			);
		},

		importBook(candidate: BookImportCandidate, status: ReadingStatus = 'want_to_read'): Promise<Book> {
			return request<Book>('/import', {
				method: 'POST',
				body: JSON.stringify({ candidate, reading_status: status })
			});
		},

		async *searchStream(
			q: string,
			type: 'title' | 'isbn' = 'title',
			mode: ImportSearchMode = 'auto'
		): AsyncGenerator<SearchStage> {
			const res = await fetch(
				`${BASE}/import/search/stream?q=${encodeURIComponent(q)}&type=${type}&mode=${mode}`,
				{ headers: authHeaders() }
			);
			if (!res.ok || !res.body) {
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			const reader = res.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;
				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';
				for (const line of lines) {
					if (line.startsWith('data: ')) {
						const text = line.slice(6).trim();
						if (text) yield JSON.parse(text) as SearchStage;
					}
				}
			}
		}
	}
};

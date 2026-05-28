import type {
	ApiKeyMeta,
	BookListResponse,
	DataExportDataset,
	DataExportFormat,
	DataImportEvent,
	DataImportMappingListItem,
	DataImportMappingRead,
	DataImportParseResponse,
	DataImportPreviewResponse,
	DataImportValidateResponse,
	DataResetResponse,
	HygieneAttribute,
	HygieneBatchUpdateRequest,
	HygieneBatchUpdateResponse,
	HygieneMissingResponse,
	ImportFieldConfig,
	Book,
	CoverCandidateList,
	BookImportCandidate,
	BookProgress,
	DailyPagesResponse,
	DashboardQuote,
	StatisticsResponse,
	LibraryStats,
	ReadingProgressEntry,
	StatusTransitionRequest,
	StatusTransitionResponse,
	ImportSearchMode,
	ReadingStatus,
	SearchStage,
	TagCloudEntry,
	SortField,
	SortOrder,
	OidcConfig,
	OidcLinkStatus,
	User,
	UserCreateResponse,
	UserAdminUpdate,
	UserSettings
} from './types';
import { apiKey, csrfToken } from './stores/auth';
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

	const method = (options?.method ?? 'GET').toUpperCase();
	if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
		const csrf = get(csrfToken);
		if (csrf) headers['X-CSRF-Token'] = csrf;
	}
	if (options?.headers) {
		Object.assign(headers, options.headers as Record<string, string>);
	}

	const res = await fetch(`${BASE}${path}`, {
		headers,
		credentials: 'same-origin',
		...options
	});

	const contentType = res.headers.get('content-type') ?? '';
	const isJson = contentType.includes('application/json');

	if (!res.ok) {
		const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
		err.status = res.status;
		if (isJson) {
			const detail = await res.json().catch(() => ({}));
			err.message = detail?.detail ?? `HTTP ${res.status}`;
			throw err;
		}
		const text = await res.text().catch(() => '');
		err.message = text || `HTTP ${res.status}`;
		throw err;
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
		}): Promise<UserCreateResponse> {
			return request<UserCreateResponse>('/auth/setup', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		login(data: { email: string; password: string }): Promise<UserCreateResponse> {
			return request<UserCreateResponse>('/auth/login', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		},

		me(): Promise<User> {
			return request<User>('/auth/me');
		},

		csrf(): Promise<{ csrf_token: string }> {
			return request<{ csrf_token: string }>('/auth/csrf');
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

		updateSettings(data: { language?: string; timezone?: string; theme?: string; custom_theme?: string | null }): Promise<UserSettings> {
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
		},

		resetData(confirmation: string): Promise<DataResetResponse> {
			return request<DataResetResponse>('/profile/reset-data', {
				method: 'POST',
				body: JSON.stringify({ confirmation })
			});
		},

		deleteOwnAccount(confirmation: string): Promise<void> {
			return request<void>('/profile/account', {
				method: 'DELETE',
				body: JSON.stringify({ confirmation })
			});
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
		}): Promise<UserCreateResponse> {
			return request<UserCreateResponse>('/users', {
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

	statistics: {
		get(): Promise<StatisticsResponse> {
			return request<StatisticsResponse>('/statistics');
		},

		getPagesPerDay(days: number = 365): Promise<DailyPagesResponse> {
			const qs = new URLSearchParams({ days: String(days) });
			return request<DailyPagesResponse>(`/statistics/pages-per-day?${qs}`);
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
		suggestions: {
			async authors(q: string, limit = 10): Promise<string[]> {
				const qs = new URLSearchParams({ q, limit: String(limit) });
				const data = await request<{ suggestions: string[] }>(`/books/suggestions/authors?${qs}`);
				return data.suggestions;
			},
			async publishers(q: string, limit = 10): Promise<string[]> {
				const qs = new URLSearchParams({ q, limit: String(limit) });
				const data = await request<{ suggestions: string[] }>(`/books/suggestions/publishers?${qs}`);
				return data.suggestions;
			},
			async tags(q: string, limit = 10): Promise<string[]> {
				const qs = new URLSearchParams({ q, limit: String(limit) });
				const data = await request<{ suggestions: string[] }>(`/books/suggestions/tags?${qs}`);
				return data.suggestions;
			}
		},

		stats(): Promise<LibraryStats> {
			return request<LibraryStats>('/books/stats');
		},

		dashboardQuote(): Promise<DashboardQuote | null> {
			return request<DashboardQuote | null>('/books/dashboard-quote');
		},

		tagCloud(limit = 20): Promise<TagCloudEntry[]> {
			const qs = new URLSearchParams();
			qs.set('limit', String(limit));
			return request<TagCloudEntry[]>(`/books/tags/cloud?${qs.toString()}`);
		},

		list(params?: {
			status?: ReadingStatus;
			q?: string;
			sort?: SortField;
			order?: SortOrder;
			smart_sort?: boolean;
			offset?: number;
			limit?: number;
		}): Promise<BookListResponse> {
			const qs = new URLSearchParams();
			if (params?.status) qs.set('status', params.status);
			if (params?.q) qs.set('q', params.q);
			if (params?.sort) qs.set('sort', params.sort);
			if (params?.order) qs.set('order', params.order);
			if (params?.smart_sort !== undefined) qs.set('smart_sort', String(params.smart_sort));
			if (params?.offset !== undefined) qs.set('offset', String(params.offset));
			if (params?.limit !== undefined) qs.set('limit', String(params.limit));
			const query = qs.toString() ? `?${qs}` : '';
			return request<BookListResponse>(`/books${query}`);
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

		progress: {
			async list(bookId: number): Promise<ReadingProgressEntry[]> {
				return request<ReadingProgressEntry[]>(`/books/${bookId}/progress`);
			},
			async create(bookId: number, page: number): Promise<ReadingProgressEntry> {
				return request<ReadingProgressEntry>(`/books/${bookId}/progress`, {
					method: 'POST',
					body: JSON.stringify({ page })
				});
			},
			async update(bookId: number, entryId: number, data: { created_at: string }): Promise<ReadingProgressEntry> {
				return request<ReadingProgressEntry>(`/books/${bookId}/progress/${entryId}`, {
					method: 'PATCH',
					body: JSON.stringify(data)
				});
			},
			async delete(bookId: number, entryId: number): Promise<void> {
				return request<void>(`/books/${bookId}/progress/${entryId}`, { method: 'DELETE' });
			},
			async latest(bookIds: number[]): Promise<BookProgress[]> {
				const qs = new URLSearchParams({ book_ids: bookIds.join(',') });
				return request<BookProgress[]>(`/books/progress/latest?${qs}`);
			}
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

	hygiene: {
		async listMissing(params: {
			attributes: HygieneAttribute[];
			match?: 'any' | 'all';
			offset?: number;
			limit?: number;
		}): Promise<HygieneMissingResponse> {
			const qs = new URLSearchParams();
			qs.set('attributes', params.attributes.join(','));
			if (params.match) qs.set('match', params.match);
			if (params.offset !== undefined) qs.set('offset', String(params.offset));
			if (params.limit !== undefined) qs.set('limit', String(params.limit));
			return request<HygieneMissingResponse>(`/hygiene/missing?${qs.toString()}`);
		},

		async batchUpdate(data: HygieneBatchUpdateRequest): Promise<HygieneBatchUpdateResponse> {
			return request<HygieneBatchUpdateResponse>('/hygiene/batch-update', {
				method: 'POST',
				body: JSON.stringify(data)
			});
		}
	},

	covers: {
		async upload(file: File): Promise<string> {
			const headers: Record<string, string> = { ...authHeaders() };
			const csrf = get(csrfToken);
			if (csrf) headers['X-CSRF-Token'] = csrf;

			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${BASE}/covers/upload`, {
				method: 'POST',
				headers,
				credentials: 'same-origin',
				body: form
			});
			if (!res.ok) {
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			const data = (await res.json()) as { cover_url: string };
			return data.cover_url;
		},

		searchCandidates(isbn: string): Promise<CoverCandidateList> {
			const qs = new URLSearchParams({ isbn });
			return request<CoverCandidateList>(`/cover-candidates/search?${qs.toString()}`);
		},

		async importFromUrl(url: string): Promise<string> {
			const data = await request<{ cover_url: string }>('/covers/import-url', {
				method: 'POST',
				body: JSON.stringify({ url })
			});
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
	},

	data: {
		async exportData(payload: { datasets: DataExportDataset[]; format: DataExportFormat }): Promise<Blob> {
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
				...authHeaders()
			};
			const csrf = get(csrfToken);
			if (csrf) headers['X-CSRF-Token'] = csrf;

			const res = await fetch(`${BASE}/data/export`, {
				method: 'POST',
				headers,
				credentials: 'same-origin',
				body: JSON.stringify(payload)
			});
			if (!res.ok) {
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			return res.blob();
		},

		async parseImportFile(file: File): Promise<DataImportParseResponse> {
			const headers: Record<string, string> = { ...authHeaders() };
			const csrf = get(csrfToken);
			if (csrf) headers['X-CSRF-Token'] = csrf;

			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${BASE}/data/import/parse`, {
				method: 'POST',
				headers,
				credentials: 'same-origin',
				body: form
			});
			if (!res.ok) {
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			return res.json() as Promise<DataImportParseResponse>;
		},

			suggestMapping(fileId: string): Promise<{ suggested_mapping: Record<string, ImportFieldConfig>; db_fields: string[] }> {
				return request<{ suggested_mapping: Record<string, ImportFieldConfig>; db_fields: string[] }>('/data/import/suggest-mapping', {
					method: 'POST',
					body: JSON.stringify({ file_id: fileId })
				});
			},

			saveMapping(payload: {
				name: string;
				source_fields: string[];
				mapping: Record<string, ImportFieldConfig>;
			}): Promise<DataImportMappingRead> {
				return request<DataImportMappingRead>('/data/import/mappings', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			},

			listMappings(): Promise<DataImportMappingListItem[]> {
				return request<DataImportMappingListItem[]>('/data/import/mappings');
			},

			getMapping(id: number): Promise<DataImportMappingRead> {
				return request<DataImportMappingRead>(`/data/import/mappings/${id}`);
			},

			deleteMapping(id: number): Promise<void> {
				return request<void>(`/data/import/mappings/${id}`, { method: 'DELETE' });
			},

			previewImport(payload: {
				file_id: string;
				mapping: Record<string, ImportFieldConfig>;
			}): Promise<DataImportPreviewResponse> {
				return request<DataImportPreviewResponse>('/data/import/preview', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			},

			validateImport(payload: {
				file_id: string;
				mapping: Record<string, ImportFieldConfig>;
				create_progress_for_read?: boolean;
			}): Promise<DataImportValidateResponse> {
				return request<DataImportValidateResponse>('/data/import/validate', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			},

			async *executeImport(payload: {
				file_id: string;
				mapping: Record<string, ImportFieldConfig>;
				import_mode: 'rollback_all' | 'continue_on_error';
				create_progress_for_read?: boolean;
				signal?: AbortSignal;
			}): AsyncGenerator<DataImportEvent> {
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
				...authHeaders()
			};
			const csrf = get(csrfToken);
			if (csrf) headers['X-CSRF-Token'] = csrf;

			const res = await fetch(`${BASE}/data/import/execute`, {
				method: 'POST',
				headers,
				credentials: 'same-origin',
				body: JSON.stringify({
					file_id: payload.file_id,
					mapping: payload.mapping,
					import_mode: payload.import_mode,
					create_progress_for_read: payload.create_progress_for_read
				}),
				signal: payload.signal
			});
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
				const chunks = buffer.split('\n\n');
				buffer = chunks.pop() ?? '';
				for (const chunk of chunks) {
					for (const line of chunk.split('\n')) {
						if (line.startsWith('data: ')) {
							const text = line.slice(6).trim();
							if (!text) continue;
							try {
								yield JSON.parse(text) as DataImportEvent;
							} catch {
								yield { event: 'error', message: 'error.importMalformedEvent' };
							}
						}
					}
				}
			}
		}
	},

	admin: {
		async downloadBackup(): Promise<Blob> {
			const res = await fetch(`${BASE}/admin/backup`, {
				method: 'GET',
				headers: { ...authHeaders() },
				credentials: 'same-origin'
			});
			if (!res.ok) {
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			return res.blob();
		},

		async validateBackup(file: File): Promise<{ valid: boolean; metadata?: Record<string, unknown>; error?: string }> {
			const headers: Record<string, string> = { ...authHeaders() };
			const csrf = get(csrfToken);
			if (csrf) headers['X-CSRF-Token'] = csrf;

			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${BASE}/admin/validate-backup`, {
				method: 'POST',
				headers,
				credentials: 'same-origin',
				body: form
			});
			if (!res.ok) {
				if (res.status === 413) {
					throw new Error('error.fileTooLarge');
				}
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			return res.json();
		},

		async restoreBackup(file: File): Promise<{ restored_books: number; restored_covers: number }> {
			const headers: Record<string, string> = { ...authHeaders() };
			const csrf = get(csrfToken);
			if (csrf) headers['X-CSRF-Token'] = csrf;

			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${BASE}/admin/restore`, {
				method: 'POST',
				headers,
				credentials: 'same-origin',
				body: form
			});
			if (!res.ok) {
				if (res.status === 413) {
					throw new Error('error.fileTooLarge');
				}
				const detail = await res.json().catch(() => ({}));
				throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`);
			}
			return res.json();
		}
	}
};

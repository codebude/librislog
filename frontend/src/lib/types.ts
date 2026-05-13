export type ReadingStatus = 'want_to_read' | 'currently_reading' | 'read' | 'did_not_finish';

export interface Book {
	id: number;
	title: string;
	author: string | null;
	isbn: string | null;
	cover_url: string | null;
	publisher: string | null;
	published_year: number | null;
	page_count: number | null;
	tags: string | null;
	notes: string | null;
	rating: number | null; // 1–5
	reading_status: ReadingStatus;
	date_added: string; // ISO datetime
	date_started: string | null;
	date_finished: string | null;
}

export interface BookImportCandidate {
	title: string;
	author: string | null;
	isbn: string | null;
	cover_url: string | null;
	publisher: string | null;
	published_year: number | null;
	page_count: number | null;
	language: string | null;
	tags: string | null;
	source: string;
}

export interface TagCloudEntry {
	tag: string;
	count: number;
}

export type ImportSearchMode = 'auto' | 'google_only';

export type SortField = 'title' | 'date_added' | 'date_started' | 'date_finished' | 'rating';
export type SortOrder = 'asc' | 'desc';

export interface StatusTransitionRequest {
	new_status: ReadingStatus;
	force_date_started?: string | null;
	force_date_finished?: string | null;
}

export interface DateConflict {
	field: 'date_started' | 'date_finished';
	existing_date: string;
	suggested_date: string;
}

export interface StatusTransitionResponse {
	book: Book;
	date_conflict: DateConflict | null;
}

export interface LibraryStats {
	total_books: number;
	books_read: number;
	books_reading: number;
	books_want_to_read: number;
	books_did_not_finish: number;
}

export interface DashboardQuote {
	quote: string;
	author: string | null;
}

export type UserRole = 'admin' | 'user';

export interface User {
	id: number;
	firstname: string;
	lastname: string;
	email: string;
	role: UserRole;
	created_at: string;
}

export interface UserCreateResponse {
	user: User;
}

export interface UserAdminUpdate {
	firstname?: string;
	lastname?: string;
	email?: string;
	role?: UserRole;
	password?: string;
}

export interface UserSettings {
	user_id: number;
	language: string;
}

export interface ApiKeyMeta {
	id: number;
	key_prefix: string;
	description: string | null;
	created_at: string;
	last_used_at: string | null;
}

export interface OidcConfig {
	enabled: boolean;
	provider_id: string | null;
	provider_name: string | null;
}

export interface OidcLinkStatus {
	linked: boolean;
	provider_name: string | null;
	oidc_email: string | null;
	oidc_name: string | null;
}

export interface ReadingProgressEntry {
	id: number;
	book_id: number;
	page: number;
	created_at: string;
	updated_at: string;
}

export interface BookProgress {
	book_id: number;
	current_page: number;
}

export type SearchStage =
	| { stage: 'open_library'; status: 'searching' }
	| { stage: 'open_library'; status: 'done'; count: number }
	| { stage: 'open_library'; status: 'error'; reason: string }
	| { stage: 'google_books'; status: 'searching' }
	| { stage: 'google_books'; status: 'done'; count: number }
	| { stage: 'google_books'; status: 'skipped'; reason: string }
	| { stage: 'google_books'; status: 'error'; reason: string }
	| { stage: 'complete'; results: BookImportCandidate[] }
	| { stage: 'error'; message: string };

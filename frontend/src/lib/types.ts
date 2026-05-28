export type ReadingStatus = 'want_to_read' | 'currently_reading' | 'read' | 'did_not_finish';

export interface Book {
	id: number;
	title: string;
	subtitle: string | null;
	author: string | null;
	isbn: string | null;
	cover_url: string | null;
	publisher: string | null;
	published_year: number | null;
	page_count: number | null;
	language: string | null;
	tags: string | null;
	notes: string | null;
	blurb: string | null;
	rating: number | null; // 1–5
	reading_status: ReadingStatus;
	date_added: string; // ISO datetime
	date_started: string | null;
	date_finished: string | null;
}

export interface BookListResponse {
	books: Book[];
	total: number;
}

export interface BookImportCandidate {
	title: string;
	subtitle: string | null;
	author: string | null;
	isbn: string | null;
	cover_url: string | null;
	publisher: string | null;
	published_year: number | null;
	page_count: number | null;
	language: string | null;
	tags: string | null;
	blurb: string | null;
	source: string;
}

export interface CoverCandidate {
	source: 'abebooks' | 'openlibrary' | 'amazon' | 'hardcover';
	url: string;
	available: boolean;
	width: number | null;
	height: number | null;
	filesize: number | null;
	content_type: string | null;
}

export interface CoverCandidateList {
	candidates: CoverCandidate[];
	query_isbn: string;
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
	skip_auto_date_started?: boolean;
	clear_date_started?: boolean;
	clear_date_finished?: boolean;
}

export interface DateConflict {
	field: 'date_started' | 'date_finished' | 'started_after_finished';
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

export interface LanguageDistribution {
	language: string | null;
	count: number;
}

export interface StatusDistribution {
	want_to_read: number;
	currently_reading: number;
	read: number;
	did_not_finish: number;
}

export interface PageBuckets {
	pages_to_read: number;
	pages_read: number;
	pages_wasted: number;
}

export interface MonthlyPages {
	month: string;
	pages: number;
}

export interface MonthlyBooks {
	month: string;
	count: number;
}

export interface YearlyBooks {
	year: number;
	count: number;
}

export interface TopAuthor {
	author: string;
	book_count: number;
	covers: TopAuthorCover[];
}

export interface TopAuthorCover {
	book_id: number;
	reading_status: ReadingStatus;
	cover_url: string;
}

export interface StatisticsResponse {
	avg_books_per_month: number | null;
	busiest_month: string | null;
	busiest_month_count: number | null;
	avg_page_count: number | null;
	most_popular_language: string | null;
	most_popular_language_count: number | null;
	language_distribution: LanguageDistribution[];
	status_distribution: StatusDistribution;
	page_buckets: PageBuckets;
	pages_read_per_month: MonthlyPages[];
	books_finished_per_month: MonthlyBooks[];
	books_finished_per_year: YearlyBooks[];
	top_authors: TopAuthor[];
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
	timezone: string;
	quote_service_enabled: boolean;
	theme: string;
	custom_theme: string | null;
}

export interface ApiKeyMeta {
	id: number;
	key_prefix: string;
	description: string | null;
	created_at: string;
	last_used_at: string | null;
}

export interface DataResetResponse {
	message: string;
	deleted: {
		books: number;
		tags: number;
		progress_entries: number;
	};
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

export interface DailyPages {
	date: string;
	pages: number;
}

export interface DailyPagesResponse {
	data: DailyPages[];
	total_days: number;
	days_with_activity: number;
	total_pages: number;
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
	| { stage: 'hardcover'; status: 'searching' }
	| { stage: 'hardcover'; status: 'done'; count: number }
	| { stage: 'hardcover'; status: 'skipped'; reason: string }
	| { stage: 'hardcover'; status: 'error'; reason: string }
	| { stage: 'google_books'; status: 'searching' }
	| { stage: 'google_books'; status: 'done'; count: number }
	| { stage: 'google_books'; status: 'skipped'; reason: string }
	| { stage: 'google_books'; status: 'error'; reason: string }
	| { stage: 'complete'; results: BookImportCandidate[] }
	| { stage: 'error'; message: string };

export type DataExportDataset = 'books' | 'progress' | 'tags' | 'covers';
export type DataExportFormat = 'csv' | 'json';

export interface DataImportParseResponse {
	file_id: string;
	format: 'csv' | 'json';
	source_fields: string[];
	sample_rows: Record<string, unknown>[];
	row_count: number;
}

export interface DataImportMappingListItem {
	id: number;
	name: string;
	created_at: string;
	updated_at: string;
	is_predefined: boolean;
}

export interface DataImportMappingRead {
	id: number;
	name: string;
	source_fields: string[];
	mapping: Record<string, ImportFieldConfig>;
	created_at: string;
	updated_at: string;
	is_predefined: boolean;
}

export interface ImportFieldConfig {
	source: string;
	transform: string | null;
}

export interface DataImportPreviewRow {
	row_number: number;
	source: Record<string, string>;
	transformed: Record<string, string | null>;
	errors: string[];
}

export interface DataImportPreviewResponse {
	preview_rows: DataImportPreviewRow[];
	row_count: number;
	errors: string[];
}

export interface DataImportValidateResponse {
	valid: boolean;
	row_count: number;
	warnings: string[];
	errors: string[];
}

export type HygieneAttribute =
	| 'author'
	| 'isbn'
	| 'publisher'
	| 'published_year'
	| 'blurb'
	| 'language'
	| 'subtitle'
	| 'page_count'
	| 'cover_url';

export interface HygieneMissingBook {
	id: number;
	title: string;
	author: string | null;
	isbn: string | null;
	publisher: string | null;
	published_year: number | null;
	blurb: string | null;
	language: string | null;
	subtitle: string | null;
	page_count: number;
	cover_url: string | null;
	missing_attributes: HygieneAttribute[];
}

export interface HygieneMissingResponse {
	books: HygieneMissingBook[];
	total: number;
	total_missing_per_attribute: Record<string, number>;
}

export interface HygieneBatchUpdateRequest {
	book_ids: number[];
	field: HygieneAttribute;
	value: string | number | null;
}

export interface HygieneBatchUpdateResponse {
	updated: number;
	skipped: number;
	skipped_ids: number[];
}

export type DataImportEvent =
	| { event: 'start'; total_rows: number }
	| { event: 'progress'; processed: number; total: number; percent: number }
	| {
			event: 'complete';
			imported: number;
			failed: number;
			failures: Array<{ row: number; error: string; data: Record<string, unknown> }>;
	  }
	| { event: 'error'; message: string };

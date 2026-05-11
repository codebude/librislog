export type ReadingStatus = 'want_to_read' | 'currently_reading' | 'read';

export interface Book {
	id: number;
	title: string;
	author: string | null;
	isbn: string | null;
	cover_url: string | null;
	publisher: string | null;
	published_year: number | null;
	page_count: number | null;
	genre: string | null;
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
	genre: string | null;
	source: string;
}

export type ImportSearchMode = 'auto' | 'google_only';

export type SortField = 'date_added' | 'rating';
export type SortOrder = 'asc' | 'desc';

export type SearchStage =
	| { stage: 'open_library'; status: 'searching' }
	| { stage: 'open_library'; status: 'done'; count: number }
	| { stage: 'google_books'; status: 'searching' }
	| { stage: 'google_books'; status: 'done'; count: number }
	| { stage: 'google_books'; status: 'skipped'; reason: string }
	| { stage: 'complete'; results: BookImportCandidate[] }
	| { stage: 'error'; message: string };

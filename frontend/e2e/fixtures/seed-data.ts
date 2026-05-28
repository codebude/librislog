export const SEED_USER = {
	email: 'e2e@test.local',
	password: 'TestPassword123!',
	firstname: 'E2E',
	lastname: 'Tester',
};

export interface SeedBook {
	title: string;
	author: string;
	isbn?: string;
	page_count?: number;
	reading_status: 'want_to_read' | 'currently_reading' | 'read' | 'did_not_finish';
	rating?: number;
	tags?: string;
	date_started?: string;
	date_finished?: string;
}

export const SEED_BOOKS: SeedBook[] = [
	{ title: 'The Great Gatsby', author: 'F. Scott Fitzgerald', isbn: '9780743273565', reading_status: 'want_to_read', rating: 4, page_count: 180 },
	{ title: 'Dune', author: 'Frank Herbert', isbn: '9780441013593', reading_status: 'want_to_read', page_count: 412 },
	{ title: 'Neuromancer', author: 'William Gibson', isbn: '9780441569595', reading_status: 'want_to_read', page_count: 271 },
	{ title: 'The Three-Body Problem', author: 'Liu Cixin', isbn: '9780765377067', reading_status: 'currently_reading', page_count: 400, date_started: '2025-01-15' },
	{ title: 'To Kill a Mockingbird', author: 'Harper Lee', isbn: '9780061120084', reading_status: 'read', rating: 5, page_count: 281, date_started: '2024-11-01', date_finished: '2024-12-15' },
	{ title: '1984', author: 'George Orwell', isbn: '9780451524935', reading_status: 'read', rating: 5, page_count: 328, date_started: '2024-10-01', date_finished: '2024-10-20' },
	{ title: 'Brave New World', author: 'Aldous Huxley', isbn: '9780060850524', reading_status: 'read', rating: 4, page_count: 311, date_started: '2024-09-01', date_finished: '2024-09-18' },
	{ title: 'Atlas Shrugged', author: 'Ayn Rand', reading_status: 'did_not_finish', page_count: 1168 },
];

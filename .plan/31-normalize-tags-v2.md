# Implementation Plan: Normalize Tags to `tags` + `book_tags` (V2)

## Goal

Move from the current comma-separated `book.tags` string to a normalized relational model:

- `tag` table: canonical user-scoped tags
- `book_tag` table: many-to-many relation between books and tags

Guarantee that no orphaned tags remain after book/tag updates or book deletion.

---

## Scope

1. Database schema and migration
2. Backend models/schemas/routers/services
3. Frontend compatibility (existing UX kept, payload shape can stay string-based in v2.0)
4. Search and tag cloud migrated to relational queries
5. Cleanup logic for orphan prevention
6. Test coverage and rollout/rollback plan

---

## 1) Data Model (Target)

## 1.1 New tables

- `tag`
  - `id` (PK)
  - `user_id` (FK -> `user.id`, indexed)
  - `name` (string, indexed)
  - `created_at` (optional)
  - Unique constraint: `(user_id, name)`

- `book_tag`
  - `book_id` (FK -> `book.id`, indexed)
  - `tag_id` (FK -> `tag.id`, indexed)
  - Composite PK or unique constraint: `(book_id, tag_id)`

## 1.2 Existing column transition

- Keep `book.tags` (string) temporarily during migration window.
- Mark it as deprecated in code comments/docs.
- Remove in a follow-up migration after all app paths use relational reads/writes.

---

## 2) Migration Strategy (Zero Data Loss)

## 2.1 Migration A: introduce normalized schema + backfill

Create Alembic migration:

1. Create `tag` and `book_tag` tables with constraints and indexes.
2. Backfill from existing `book.tags` strings:
   - Iterate all books with non-null/non-empty `book.tags`.
   - Split by comma, trim whitespace, drop empties.
   - Normalize for dedupe policy (recommended for v2.0):
     - storage canonicalization: trim + collapse internal whitespace
     - preserve user-facing case (or choose lowercase canonical; decide once)
   - Upsert `tag(user_id, name)` per tag.
   - Insert into `book_tag(book_id, tag_id)` with conflict ignore.
3. Add verification SQL in migration comments (counts before/after).

## 2.2 Migration B (later): remove deprecated column

After at least one release cycle and validation:

1. Drop `book.tags` column.
2. Remove transitional fallback code.

---

## 3) Orphan Prevention Design

## 3.1 Book deletion path

When deleting a book:

1. Delete `book_tag` rows for the book (or rely on FK `ON DELETE CASCADE`).
2. Cleanup unused tags for that user in same transaction:

```sql
DELETE FROM tag t
WHERE t.user_id = :user_id
  AND NOT EXISTS (
    SELECT 1
    FROM book_tag bt
    JOIN book b ON b.id = bt.book_id
    WHERE bt.tag_id = t.id
      AND b.user_id = t.user_id
  );
```

This guarantees no orphan tags remain for that user.

## 3.2 Book update path

On tag edits:

1. Parse incoming tag string/list -> normalized unique set.
2. Upsert needed tags.
3. Replace book-tag links atomically (delete stale links, insert desired links).
4. Run same orphan cleanup for affected user.

## 3.3 Optional DB-level safeguard

- Add periodic cleanup job (maintenance command) as defense-in-depth.
- Main correctness remains transactionally enforced in write paths.

---

## 4) Backend Changes

## 4.1 Models

Files:

- `backend/app/models.py`

Add `Tag` and `BookTag` SQLModel entities, FK constraints, indexes.

## 4.2 Schemas/API contract

Recommended v2.0 API compatibility mode:

- Keep API `BookRead.tags` as `string | null` for frontend stability.
- Backend composes this from relational tags (`", ".join(...)`).
- Accept incoming `tags` string in create/update to avoid frontend churn.

Optional v2.1:

- Extend API with `tags_list: string[]` and migrate frontend gradually.

## 4.3 Router/service logic

Files:

- `backend/app/routers/books.py`
- potentially new helper module, e.g. `backend/app/services/tags.py`

Implement helpers:

- `parse_tags(raw: str | None) -> list[str]`
- `sync_book_tags(session, user_id, book_id, tags)`
- `cleanup_orphan_tags(session, user_id)`

Apply in:

- create book
- update book
- delete book
- import book

## 4.4 Search and tag cloud

Replace string `LIKE` on `book.tags` with relational query:

- book search (`q`) should match title, author, and tag names via joins.
- tag cloud should aggregate from `tag` + `book_tag` grouped by tag.
- apply `limit` in SQL query.

---

## 5) Frontend Plan

Keep current UX with badge/tag input unchanged.

## 5.1 Minimal frontend changes for v2.0

- No mandatory UI changes if backend keeps `tags` string contract.
- Keep existing components:
  - `TagInput.svelte`
  - `BookDrawer.svelte`
  - `AddBookModal.svelte`
  - `BookDetailDialog.svelte`
  - Dashboard tag cloud/search behavior

## 5.2 Optional v2.1 enhancement

- Move to `tags_list: string[]` in API for cleaner client semantics.

---

## 6) Importer Integration

Files:

- `backend/app/services/book_import.py`
- `backend/app/routers/import_.py`

No functional change to mapping logic required (still outputs `tags` text), but persistence path must use relational sync helper instead of writing `book.tags` as source of truth.

---

## 7) Testing Plan

## 7.1 Migration tests

- Backfill preserves all tags from `book.tags`.
- Duplicate tags collapse correctly per user.
- Multiple books can reference same tag.

## 7.2 Backend unit/integration tests

Add/adjust in:

- `backend/tests/test_books.py`
- `backend/tests/test_import.py`

Cases:

1. Create book with tags -> `tag` + `book_tag` rows created.
2. Update tags replaces associations correctly.
3. Deleting one of multiple books sharing a tag keeps tag.
4. Deleting last book referencing a tag removes orphan tag.
5. Search by tag still works.
6. Tag cloud returns correct counts and respects `limit`.
7. Multi-user isolation: same tag text across users must remain isolated.

## 7.3 Regression checks

- Full backend suite green.
- Frontend `npm run check` green.

---

## 8) Rollout Steps

1. Implement migration A and backend relational read/write logic.
2. Deploy with compatibility mode (`BookRead.tags` still exposed).
3. Run DB migration and smoke test:
   - create/update/delete books with tags
   - dashboard tag cloud
   - dashboard search by tag
4. Observe for one release cycle.
5. Implement migration B to drop deprecated `book.tags` column.

---

## 9) Risks and Mitigations

- **Risk:** tag normalization surprises users (case/spacing).
  - **Mitigation:** document and keep deterministic normalization.
- **Risk:** query complexity/regressions in search.
  - **Mitigation:** targeted tests + SQL indexes.
- **Risk:** orphan tags from missed write path.
  - **Mitigation:** shared service helper + post-write cleanup in all mutate paths + optional maintenance cleanup.

---

## 10) Estimated Effort

- Schema + migration + backfill: 0.5-1 day
- Backend logic + tests: 1-2 days
- Frontend compatibility verification: 0.5 day
- Hardening + rollout + cleanup migration: 0.5-1 day

Total: ~2.5-4.5 days.

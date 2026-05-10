# LibrisLog — Delete Cover Image When Book Is Deleted

## Goal

When a book is deleted, remove its locally stored cover image too, but only if no
other book still references the same local cover file.

This keeps `./data/covers/` from accumulating orphaned files while avoiding
breaking shared cover references.

---

## Current Behavior

`DELETE /api/books/{book_id}` removes the `Book` row only.  It does not inspect
`cover_url`, so locally cached cover images remain on disk after deletion.

---

## Planned Implementation

1. Update `app/routers/books.py` delete flow.
2. Detect whether the book’s `cover_url` points to a local cover (`/api/covers/...`).
3. Before deleting the file, query for any other books using the same local cover URL.
4. If no other book references it, remove the file from `settings.covers_dir`.
5. Keep delete behavior non-fatal if file removal fails: delete the book record,
   log the failure, and continue returning `204`.

---

## Notes

- Only local cached covers should be deleted.
- External URLs should be ignored.
- File deletion should be safe against path traversal by resolving the stored
  filename under `covers_dir` only.
- If the file is already missing, deletion should still succeed.

---

## Test Plan

### Update `backend/tests/test_books.py`

Add tests for these cases:

1. `test_delete_book_removes_local_cover_file`
   - Create a book with a local `cover_url`.
   - Create the matching file in `tmp_path`.
   - DELETE the book.
   - Assert the response is `204` and the cover file is gone.

2. `test_delete_book_keeps_shared_cover_file`
   - Create two books that reference the same local cover URL.
   - DELETE one book.
   - Assert the file still exists because the other book still uses it.

3. `test_delete_book_ignores_external_cover_url`
   - Create a book whose `cover_url` is an external URL.
   - DELETE the book.
   - Assert the response is `204` and no filesystem cleanup is attempted.

4. `test_delete_book_still_succeeds_when_cover_file_missing`
   - Create a book with a local cover URL but no matching file on disk.
   - DELETE the book.
   - Assert the response is `204`.

---

## Files Expected To Change

- `backend/app/routers/books.py`
- `backend/tests/test_books.py`
- Possibly `backend/app/services/cover_storage.py` if shared cleanup helpers are needed

---

## Out Of Scope

- Background cleanup of orphaned covers already left behind by old deletes.
- Reference counting in the database.
- Removing unused cover files created by failed imports.

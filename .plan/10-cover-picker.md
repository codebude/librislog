# LibrisLog — Cover Picker (Upload & URL) for Manual Add and Edit

## Goal

Allow users to attach a cover image when creating a book manually or editing
an existing one, via two input modes:

1. **File upload** — drag & drop or file-browser button; image is immediately
   uploaded to `POST /api/covers/upload` and stored locally.
2. **URL input** — paste an external image URL; the backend downloads and caches
   it locally when the book is saved.

---

## Motivation

Books imported via the Search & Import tab already receive covers automatically.
Books added manually have no cover path.  Likewise, editing a book offered no
way to change or add a cover image.

---

## Backend Changes

### `app/services/cover_storage.py` — `save_uploaded_cover()`

New synchronous helper that accepts raw image bytes and a content-type string,
validates them (image MIME type, ≥ 5 KB), deduplicates by SHA-256 content hash,
and writes the file atomically under `covers_dir`.

```
save_uploaded_cover(body: bytes, content_type: str, covers_dir: str | Path) -> str | None
```

- Dedup key: `sha256(body)[:32]` (content hash, unlike URL-downloaded covers
  which use `sha256(url)[:32]`).
- Atomic write: `{filename}.tmp` → `os.replace()`.
- Returns local filename on success, `None` on failure.

### `app/routers/covers.py` — `POST /api/covers/upload`

```
POST /api/covers/upload
Content-Type: multipart/form-data
field: file (UploadFile)

→ 200  {"cover_url": "/api/covers/<filename>"}
→ 422  {"detail": "Invalid image or file is too small (minimum 5 KB)."}
```

FastAPI `UploadFile` / `File(...)` — requires `python-multipart` dependency.
Fixed-path route `/upload` takes precedence over the parameterised `/{filename}`
route (FastAPI prefers fixed segments over path parameters).

### `app/routers/books.py` — async `create_book` and `update_book`

Both endpoints are now `async def` so they can `await download_cover()`.

**`create_book`**

- If `cover_url` is an external HTTP(S) URL, open an `httpx.AsyncClient` and
  call `download_cover()`.
- On success replace `cover_url` with `/api/covers/<filename>`.
- On failure (network error, too small, non-image) fall back silently to the
  original external URL.
- Local `/api/covers/` URLs are passed through unchanged (no re-download).

**`update_book`**

- Same external-URL download logic as `create_book`.
- If `cover_url` changed *and* the old value was a local cover, check whether
  any other book shares that URL; if not, delete the old cover file.

Helper `_is_external_url(url)` centralises the `http://`/`https://` check.

---

## Frontend Changes

### `src/lib/api.ts` — `api.covers.upload(file)`

```ts
covers: {
  upload(file: File): Promise<string>   // returns cover_url
}
```

Sends a multipart `POST /api/covers/upload`; returns the `cover_url` string.

### `src/lib/components/CoverPicker.svelte` — new component

Props:

| prop | type | default |
|------|------|---------|
| `value` | `string \| null` (bindable) | `null` |
| `disabled` | `boolean` | `false` |

States / behaviour:

- **No value** — shows a dashed drop zone ("Drag & drop or browse") and a URL
  input with a "Use URL" button.
- **Drop zone** — `ondrop` / `ondragover` / `ondragleave` handlers; clicking
  the zone opens the hidden `<input type="file" accept="image/*">`.
- **File selected** — calls `api.covers.upload(file)` immediately; sets `value`
  to the returned `cover_url`; shows a spinner during upload.
- **URL input** — pressing Enter or clicking "Use URL" sets `value` directly to
  the trimmed URL string (the backend downloads it on save).
- **Has value** — shows `<img src={value}>` preview plus a "Remove" button that
  resets `value` to `null`.
- Upload errors surfaced via `toasts.add()`.

### `src/lib/components/AddBookModal.svelte`

- Import `CoverPicker`.
- Add `cover_url` state (initially `null`); reset it in `reset()`.
- Include `cover_url` in `api.books.create()` payload.
- Render `<CoverPicker bind:value={cover_url} disabled={submitting} />` between
  the Notes field and the modal action row.

### `src/lib/components/BookDrawer.svelte`

- Import `CoverPicker`.
- Add `cover_url` state; sync it from `book.cover_url` in the `$effect`.
- Include `cover_url` in `api.books.update()` payload.
- Remove the read-only cover `<img>` from the "Cover + meta" block (replaced by
  the editable picker in the form).
- Render `<CoverPicker bind:value={cover_url} disabled={saving} />` after the
  Notes field.

---

## Dependency Added

`python-multipart==0.0.28` — required by FastAPI to parse `multipart/form-data`
file uploads.

---

## Test Plan

### `backend/tests/test_cover_storage.py` — `save_uploaded_cover` unit tests

| test | assertion |
|------|-----------|
| `test_save_uploaded_cover_success` | valid JPEG bytes → file written, `.jpg` extension |
| `test_save_uploaded_cover_png` | `image/png` → `.png` extension |
| `test_save_uploaded_cover_too_small` | < 5 KB → `None`, no file written |
| `test_save_uploaded_cover_non_image` | `text/plain` → `None` |
| `test_save_uploaded_cover_dedup` | same bytes twice → same filename, original not overwritten |
| `test_save_uploaded_cover_no_tmp_leftover` | no `.tmp` file after success |
| `test_save_uploaded_cover_content_type_with_params` | `image/jpeg; charset=…` → `.jpg` |

### `backend/tests/test_covers.py` — upload endpoint tests

| test | assertion |
|------|-----------|
| `test_upload_cover_valid_jpeg` | 200 + `cover_url` starts with `/api/covers/`, file exists |
| `test_upload_cover_valid_png` | filename ends with `.png` |
| `test_upload_cover_too_small_returns_422` | 422 |
| `test_upload_cover_non_image_returns_422` | 422 |
| `test_upload_cover_dedup_returns_same_url` | two identical uploads → same `cover_url` |

### `backend/tests/test_books.py` — create/update cover integration tests

| test | assertion |
|------|-----------|
| `test_create_book_with_external_cover_downloads_local` | cover_url becomes `/api/covers/…`, file written |
| `test_create_book_cover_download_fail_falls_back_to_external` | original external URL stored |
| `test_create_book_local_cover_url_not_re_downloaded` | `download_cover` not called for `/api/covers/` URL |
| `test_update_book_with_external_cover_downloads_local` | cover_url becomes local after PATCH |
| `test_update_book_cover_change_deletes_old_local_cover` | old cover file removed |
| `test_update_book_cover_change_keeps_shared_cover` | file kept when another book shares it |

`download_cover` is monkeypatched via `monkeypatch.setattr(books_router, "download_cover", …)`
to avoid real HTTP traffic.

---

## Files Changed

| file | change |
|------|--------|
| `backend/app/services/cover_storage.py` | `save_uploaded_cover()` added |
| `backend/app/routers/covers.py` | `POST /api/covers/upload` added |
| `backend/app/routers/books.py` | `create_book` + `update_book` → `async def`; cover download + cleanup |
| `backend/pyproject.toml` | `python-multipart` dependency added |
| `backend/tests/test_cover_storage.py` | 7 new unit tests for `save_uploaded_cover` |
| `backend/tests/test_covers.py` | 5 new upload endpoint tests |
| `backend/tests/test_books.py` | 6 new create/update cover tests |
| `frontend/src/lib/api.ts` | `api.covers.upload()` added |
| `frontend/src/lib/components/CoverPicker.svelte` | new component |
| `frontend/src/lib/components/AddBookModal.svelte` | `CoverPicker` wired in |
| `frontend/src/lib/components/BookDrawer.svelte` | `CoverPicker` wired in |

---

## Out Of Scope

- Cropping or resizing uploaded images server-side.
- Enforcing a maximum upload size beyond what `python-multipart` / the OS allows
  (a future Nginx/Traefik body-size limit handles that at the infrastructure level).
- Cleaning up orphaned uploaded covers when the modal is cancelled before saving
  (acceptable for a single-user app).

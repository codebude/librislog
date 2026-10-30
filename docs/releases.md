# Release Notes

All LibrisLog releases, newest first — what's new, what was fixed, and anything you need to know before upgrading.

> **Upgrading:** releases are backwards compatible. Database migrations run automatically when the container starts (`alembic upgrade head`), so upgrading is a drop-in replacement. We always recommend [taking a backup](/guide/using-librislog/administration#backup-restore) before an upgrade.

You can also browse the [GitHub Releases](https://github.com/codebude/librislog/releases) page and the [full changelog](https://github.com/codebude/librislog/commits/main).

## Unreleased

::: tip ⭐ v1.12.0 - Mass Tag Editor, Profile Pictures & Authentication Methods
LibrisLog v1.12.0 adds a Mass Tag Editor page for adding or removing tags on many books at once, and profile pictures with three selectable sources: the existing animal avatar, a locally cached OIDC picture, and a manually uploaded image with a built-in cropper. Public profiles gain a separate profile picture toggle. It also adds two opt-in authentication options: password login can be disabled once single sign-on is in use, and a trusted reverse proxy can sign users in from a forwarded header. Existing accounts keep their animal avatar and existing share links stay unchanged after upgrading, and the new options need no manual data migration.
:::

## Latest Release

::: tip ⭐ v1.11.0 — Reading Sessions & Re-reads
LibrisLog v1.11.0 lets books be read more than once. Each reading is tracked as its own session with independent start and finish dates, and a "Read again" action starts a fresh reading without overwriting earlier dates or progress. A reading history in the book detail dialog lets you add past reads and edit or delete individual sessions, progress restarts per session, and re-read books show a "read ×N" badge. Statistics now distinguish unique books from total completions (with a new "Total reads" card), and the timeline lists one row per completed read, marking re-reads. Data migrates automatically on upgrade.
:::

### All releases

| Version | Date | Type |
|---|---|---|
| [v1.12.0](#v1-12-0-mass-tag-editor-profile-pictures-authentication-methods) | Unreleased | Feature release |
| [v1.11.0](#v1-11-0-reading-sessions-re-reads) | 2026-10-24 | Feature release |
| [v1.10.0](#v1-10-0-more-book-sources-upgrades) | 2026-10-18 | Feature release |
| [v1.9.0](#v1-9-0-smarter-import-search-input-ux) | 2026-09-15 | Feature release |
| [v1.8.0](#v1-8-0-camera-zoom-control-optional-telemetry) | 2026-09-02 | Feature release |
| [v1.7.0](#v1-7-0-reading-streaks-goals) | 2026-08-26 | Feature release |
| [v1.6.0](#v1-6-0-reading-progress-possession-tracking) | 2026-08-23 | Feature release |
| [v1.5.2](#v1-5-2-maintenance) | 2026-06-22 | Maintenance |
| [v1.5.1](#v1-5-1-maintenance) | 2026-06-22 | Maintenance |
| [v1.5.0](#v1-5-0-password-reset-usability) | 2026-06-22 | Feature release |
| [v1.4.0](#v1-4-0-embeddable-views-arm64) | 2026-06-14 | Feature release |
| [v1.3.1](#v1-3-1-maintenance) | 2026-06-09 | Maintenance |
| [v1.3.0](#v1-3-0-more-languages) | 2026-06-09 | Feature release |
| [v1.2.2](#v1-2-2-maintenance) | 2026-06-08 | Maintenance |
| [v1.2.1](#v1-2-1-import-reliability-multi-user-consistency) | 2026-06-08 | Feature release |
| [v1.2.0](#v1-2-0-startup-screen-update-checks) | 2026-06-01 | Feature release |
| [v1.1.1](#v1-1-1-maintenance) | 2026-06-01 | Maintenance |
| [v1.1.0](#v1-1-0-polish-missing-covers) | 2026-05-31 | Feature release |
| [v1.0.0](#v1-0-0-initial-release) | 2026-05-28 | Initial release |

---

## v1.12.0: Mass Tag Editor, Profile Pictures & Authentication Methods

<Badge type="tip" text="Feature release" /> <Badge type="info" text="Unreleased" />

**Summary:** LibrisLog v1.12.0 adds a Mass Tag Editor page for adding or removing tags on many books at once, profile pictures with three selectable sources (animal avatar, cached OIDC picture, and manual upload with a circular cropper), a separate profile picture toggle for public profiles, and two opt-in authentication options. Administrators can disable password login once single sign-on is in use, and deployments behind an authenticating reverse proxy can sign users in automatically from a forwarded header.

**Features**
- 🏷️ **Mass Tag Editor page.** New page at `/tag-editor`, reachable from Profile → Manage my data, with the same filter bar as the library (search, status, medium, acquisition, tag) plus row selection and "select all matching filters".
  - 🔁 **Add and remove in one step.** Both fields in a single action, applied in chunks of 500 books with progress reporting.
  - ⚠️ **Case-variant warning.** Tags that differ only in capitalization from an existing tag are flagged, with a one-click shortcut to reuse the existing spelling.
  - 🧹 **Orphan tag cleanup.** Tags left on no book are deleted automatically.
- 🖼️ **Profile pictures with three sources.** Choose the generated animal avatar, the picture from your OIDC provider, or an uploaded image. Existing accounts keep the animal avatar, so nothing changes until you pick a source.
  - ✂️ **Built-in cropper.** Uploaded images open in a round cropper before they are sent to the server. The backend validates the image, resizes it to at most 512 pixels, strips metadata, and stores it as WebP under `AVATARS_DIR`.
  - 🏷️ **OIDC pictures refresh on login.** The provider's `picture` claim is cached locally and refreshed on every OIDC login. Linking an account caches the picture without switching the avatar automatically; unlinking removes the cache and falls back to the uploaded picture or the animal avatar.
  - 👁️ **Separate public profile picture toggle.** Share links get their own **Profile picture** section. It is off by default, so existing links keep their current appearance. The tokenized avatar endpoint only serves the image when that section is enabled.
  - 🧹 **Avatar cleanup.** The hourly maintenance task also removes orphaned avatar files that are no longer referenced by a user image row.
- 🔐 **Disable password login.** `PASSWORD_LOGIN_ENABLED=false` hides the email/password form and "Forgot password?" link and makes the login, forgot-password, and reset-password endpoints return `403`. First-admin setup still works, so a new instance can always be bootstrapped. The setup page warns when single sign-on should be linked before logging out.
- 🌐 **Trusted reverse-proxy authentication.** `TRUSTED_PROXY_AUTH_ENABLED=true` signs a user in automatically when a trusted proxy forwards an identity in a configurable header. The header, trusted IPs or CIDR ranges, and an optional shared secret are configurable, and `TRUSTED_PROXY_AUTH_USER_MAP` can translate proxy usernames to account emails when the proxy name is not the email itself. The feature fails closed when misconfigured, rejects ambiguous email matches, and ignores unknown values.
- 🔁 **Automatic OIDC redirect.** `OIDC_AUTO_REDIRECT=true` sends the login page straight to the provider when `PASSWORD_LOGIN_ENABLED=false`. Failed attempts return to the login page with an error instead of looping.
- ⚙️ **Config API.** `GET /api/config` now exposes `password_login_enabled` and the effective `trusted_proxy_auth_enabled` state so the login page can adapt. The profile password field is hidden while password login is disabled.
- 🌍 **Translations.** New login and setup messages in English, German, Spanish, French, and Chinese.

**Improvements**
- 🔍 **Exact tag filters.** `GET /api/books` and the new `GET /api/books/ids` accept `tag` and `exclude_tag` for exact tag name filtering.
- 📋 **Tag listing.** New `GET /api/tags` returns all tags with usage counts.
- 📚 **Authentication documentation.** New configuration reference and administration guidance, including a Traefik BasicAuth example and recovery steps for password lockout.
- ⚙️ **Profile picture settings.** `AVATARS_DIR`, `AVATAR_MAX_UPLOAD_MB`, `AVATAR_MAX_DIMENSION`, `AVATAR_QUALITY`, `AVATAR_FETCH_TIMEOUT_SECONDS`, and `AVATAR_FETCH_MAX_BYTES` control avatar storage, upload limits, image normalisation, and OIDC picture downloads. See the [Configuration guide](/guide/configuration#profile-pictures).

**Dependencies**
- ⬆️ Updated backend and frontend dependencies, including FastAPI, Pydantic, SQLAlchemy, Alembic, Starlette, pytest, Playwright, Scrapling, curl-cffi, SvelteKit, Svelte, Vite, Vitest, and Chart.js. TypeScript 7 was intentionally deferred because it is a major upgrade.
- ➕ Added Pillow for server-side avatar validation and normalisation, and cropperjs for the profile picture cropper.

**Bug fixes**
- 🔐 **OIDC redirect safety net.** A loopback `PUBLIC_APP_URL` such as the old `.env.example` value `http://localhost:5173` is ignored for non-local requests, so existing installations do not redirect users to localhost after upgrading. A startup warning explains how to set it correctly.
- 🔗 **Configurable OIDC callback origin.** `OIDC_CALLBACK_BASE_URL` lets the backend advertise a different public origin for the OIDC callback routes, which fixes login behind proxies that rewrite the `Host` header, such as the Vite dev server on a custom LAN hostname. Left empty, the callback URI is still built from the request as before.

**Breaking changes:** None. The profile picture feature adds an automatic database migration for `user.avatar_source` and the `user_image` table; no manual action is needed. Existing accounts keep the animal avatar, and existing share links keep their current sections because the new **Profile picture** toggle is off by default. Existing endpoints keep their behaviour; only two optional query parameters and new endpoints were added. Both authentication features are disabled by default. Existing installations keep password login and behave exactly as before.

[Compare with v1.11.0](https://github.com/codebude/librislog/compare/v1.11.0...HEAD)

---

## v1.11.0: Reading Sessions & Re-reads

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-10-24" />

**Summary:** Books can now be read more than once. Each reading is tracked as its own session with independent start and finish dates, and a "Read again" action starts a fresh reading without overwriting earlier dates or progress. A reading history in the book detail dialog lets you add past reads and edit or delete individual sessions, progress restarts per session, and re-read books show a "read ×N" badge. Statistics now distinguish unique books from total completions (with a new "Total reads" card), and the timeline lists one row per completed read, marking re-reads. Data migrates automatically on upgrade.

**Features**
- 📖 **Multiple reading sessions per book.** Each book keeps a list of reading periods (start and finish dates) so re-reads never overwrite earlier dates. A new `reading_session` table stores them; `Book.date_started` / `Book.date_finished` remain a mirror of the current session, so every existing consumer (sorting, timeline, statistics, import/export) keeps working unchanged
- 🔁 **"Read again" action.** A ghost button in the book detail dialog starts a new reading session for a finished book. Earlier sessions and their progress stay untouched, and the progress bar resets to 0 %. This is the recommended way to re-read; changing a book's status from "read" to "currently reading" via the edit drawer is the legacy correction path and can keep the previous finish date
- 📜 **Reading history.** A collapsible block in the book detail dialog lists every session (#, started, finished, status, pages) with per-row edit and delete, plus "Add a past reading" for back-filling handwritten history
- 🏷️ **"read ×N" badge.** Cards, list rows and the book detail dialog show a small badge once a book has been read at least twice
- 📊 **Statistics distinguish unique books from total completions.** A new "Total reads" card shows the number of completed reads (with a "N re-read books" sub-line). `books_finished_per_month/year`, the `books_per_month/year` goals, and `pages_read` now count every completion; "Pages read" in the bucket still counts each book once, so no single-session user sees any change
- 📅 **Timeline lists one row per completed read**, with a "Reread" badge from the second read onward
- 🔄 **Migration is automatic.** Existing books get one session from their dates; reading progress is linked to it. A book with a single session behaves bit-identically to before

**Improvements**
- 🛡️ **Session-aware progress and statistics.** Pages-per-month and pages-per-day no longer discard a re-read's pages as negative deltas (a long-standing bug where a restart at page 0 made every later delta negative)
- 📦 **Export includes a `sessions` dataset.** Re-read history is exported as a flat, book-ID-referenced `sessions` dataset (for auditing and third-party tools). Full re-read history is preserved through [backup and restore](/guide/using-librislog/administration), which copies the whole database
- 🔁 **Full backup/restore upgraded.** Restoring a backup from an older LibrisLog release migrates the schema automatically (the new tables and columns are added on restore)
- 🎯 **Date-conflict dialog gains a "Start a new read" action** for finished books moved back to "Currently reading", keeping the earlier reads in history

**Breaking changes:** None. Existing installs keep working untouched: every book with a single session behaves and scores identically to before, and data migrates automatically on upgrade. Downgrading to a previous release drops re-read history (the `reading_session` table is removed).

[Compare with v1.10.0](https://github.com/codebude/librislog/compare/v1.10.0...HEAD)

---

## v1.10.0: More Book Sources & Upgrades

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-10-18" />

**Summary:** Adds four more metadata sources to the import search, brings back coverage for non-English editions that Open Library misses, adds an on/off switch for every import source, keeps the Add Book dialog header reachable while scrolling, and updates the frontend framework and dependency set.

**Features**
- 📚 **Bibliothèque nationale de France (BnF)** as a search source, queried over the public SRU endpoint. No API key needed. Strong coverage of French editions: an ISBN such as `9791020923554` returns no result from Open Library but a full record from BnF, with title, subtitle, authors, publisher, year, page count, language, and subject headings. BnF answers one ISBN with several records, including a commercial barcode stub; those are grouped per ISBN so only the richest record is imported
- 🔗 **Inventaire.io** as a search source, queried over its public entities API. No API key needed. It aggregates data from several national libraries and is the only new source that supplies cover images. Inventaire answers ISBN lookups only, because it exposes no title search, so it is reported as skipped on a title search instead of returning an empty result
- 🏛️ **Library of Congress** as a search source, queried over the official SRU server. No API key needed. Coverage is US and English oriented, so it complements rather than replaces the other sources. **This source is only reachable over plain HTTP**, so its queries and responses travel unencrypted; it can be switched off if that is not acceptable in your network. See the [Configuration guide](/guide/configuration)
- 📕 **Deutsche Nationalbibliothek** as a search source, queried over its public SRU endpoint. No API key needed. Strong coverage of German-language editions, and unlike the Library of Congress it answers both title and ISBN searches over HTTPS. Records are read as MARC21, so the subtitle, publisher, year, page count, language, subject headings and description all come through, and co-authors catalogued as added entries are included alongside the lead author. Four cataloguing quirks are handled rather than shown raw: the non-sorting markers the DNB embeds around articles such as the "Der" in *Der Zauberberg* are stripped, a record that flags its own ISBN as misprinted is imported without one instead of with a number that identifies a different book, editors or translators listed as added entries are not reported as authors, and an inverted catalogued name is turned back into reading order without eating the period on a real initial or title. One quirk is passed through unchanged: the DNB transliterates umlauts in its titles, so *Das Maß* comes back as *Das Mass der Erde*
- 🔀 **Every import source can be switched on or off individually.** Seven new `*_IMPORT_SEARCH_ENABLED` settings cover Open Library, BnF, Inventaire.io, the Library of Congress, the Deutsche Nationalbibliothek, Hardcover, and the Google Books fallback. Sources that are switched off are not queried at all
- 🔑 **Hardcover and Google Books are set to `false` in `.env.example`.** Neither can answer a query without credentials, so the example config recommends switching them off unless a token or key is configured. The built-in default stays `true`, so existing installs that never set the variable keep their current behavior after upgrading. A source left on without its credential is reported as skipped and makes no request
- 🚦 **Startup guard for unusable sources.** If no source can answer, the backend refuses to start and names the settings to change, instead of silently returning no search results forever. That includes the case where only Hardcover and Google Books are enabled without their credentials
- 🌍 **Localized source names.** Import sources are shown under their translated name in the search progress list and in the edition chips, in all five UI languages

**Improvements**
- 🌐 **Configurable backend address.** The frontend webserver proxies `/api` to `BACKEND_ADDR` (default `http://backend:8000`) instead of a hardcoded backend host, so the web container can reach a backend outside the bundled `docker-compose.yml`. A value that would break API routing, such as one with a trailing slash, is reported when the container starts. See the [Configuration guide](/guide/configuration)
- 📌 **Sticky Add Book dialog header.** The dialog title and the close button stay pinned to the top of the window while the content scrolls, so closing the dialog no longer requires scrolling back up after a long list of results
- 🔍 **Search results report each source.** The progress list names every source that was queried, including those that were skipped and why

**Dependencies**
- ⬆️ Updated backend and frontend dependencies, most notably SvelteKit 3 and Vitest 5. Building the frontend from source now needs Node.js 22.17 or newer

**Bug fixes / security**
- 🛡️ **Remote SRU responses are parsed with entity expansion disabled.** The BnF, Library of Congress and Deutsche Nationalbibliothek responses are untrusted remote XML and are now parsed defensively, so a hostile or malformed response cannot exhaust memory or read local files through entity references
- 🛡️ **Import rejects cover URLs that point at private addresses.** A book candidate is submitted by the client, so its cover URL is untrusted input. URLs resolving to loopback, private, or link-local addresses are now rejected before download instead of being fetched

**Contributors:** Thank you to **[@mj0nez](http://github.com/mj0nez)** for making the backend address of the webserver configurable.

**Breaking changes:** None. Existing installs keep working untouched: every source defaults to `true`, so no configured source is lost on upgrade. To follow the recommended configuration, set `HARDCOVER_IMPORT_SEARCH_ENABLED=false` and `GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=false` unless you have configured a token or key. If your deployment blocks outbound plain HTTP on port 210, set `LIBRARY_OF_CONGRESS_IMPORT_SEARCH_ENABLED=false`.

[Compare with v1.9.0](https://github.com/codebude/librislog/compare/v1.9.0...v1.10.0)

---

## v1.9.0: Smarter Import Search & Input UX

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-09-15" />

**Summary:** Adds shareable read-only public profile pages with configurable access and content, groups duplicate import-search results into expandable edition groups, lets you collect search results in an import basket and import them all at once, supports multiple parallel import searches, makes running searches cancelable, adds Excel (XLSX) file import, adds a Bookstats import preset, adds configurable reading-date automation, introduces an adaptive date input with a native picker, adds optional book media and medium statistics, supports localized medium and possession searches, detects insecure camera contexts, and fixes timezone handling in the daily page statistics and progress log editing.

**Features**
- 📚 **Edition groups in the import search**: results from different providers that describe the same book (same ISBN, or same title and authors) are now grouped into expandable entries with an "N results" badge. Compare the variants side by side and import the one you want; no result is dropped anymore. The selected edition is highlighted with a border and a "Selected" badge, and every edition row shows a pointer cursor, hover feedback, and a keyboard focus ring. See the [Library guide](/guide/using-librislog/library#how-results-are-grouped) for the exact grouping rules
- 🗂️ **Optional book medium**: classify books as Print, eBook, Audiobook, Comic / Graphic Novel, or Magazine / Newspaper from manual entry, search import, and book editing. Mediums can be filtered in the library, searched with `medium:`, imported/exported, and reviewed in the statistics distribution
- 🌍 **Localized search values**: `medium:` and `possession:` searches accept both their original enum keys and localized display values, such as `medium:Hörbuch` and `possession:Im Besitz`
- 🛑 **Cancelable book search**: while an import search is running, the Search button becomes a Cancel button, so you can stop the request and refine your query
- ⌨️ **Escape closes dialogs and drawers**: overlays such as the sidebar, the book drawer, and the import modal can now be closed with the Escape key
- 📅 **Adaptive date input**: date fields in the book form now use a segmented year/month/day input that no longer assumes the month or day after the first keystroke, validates values as you type, and accepts pasting a complete date. A calendar button next to the field opens the native date picker
- 🌐 **Searchable timezone picker**: the timezone setting on the profile page is now a searchable dropdown covering all IANA timezones
- 📷 **Secure context detection in the barcode scanner**: if LibrisLog is served outside a secure context (plain HTTP on a remote host), the scan button is hidden and the scanner explains why the camera cannot start, instead of showing a black box. See the [Library guide](/guide/using-librislog/library#isbn-barcode-scan) for details
- 🎥 **Active camera name in the scanner**: the barcode scanner now shows the name of the active camera in a badge next to the switch button, so you always know which lens is being used
- 🔗 **Heimdall dashboard integration**: new documentation for the LibrisLog enhanced app, which shows your reading statistics directly on [Heimdall](https://github.com/linuxserver/Heimdall) tiles
- 🔗 **Shareable public profile pages**: create named, read-only profile URLs from the Profile page. Configure each link independently for public or logged-in-only access, selected profile sections and statistics, language, and an optional expiration date. Shared pages include responsive book cards, a mobile-safe reading timeline with incremental loading and hidden-book hints, full-library search with incremental loading, selectable 12-month/3-year/all-time trend ranges with value tooltips, distribution and rating panels, and the owner's generated avatar. Existing links can be copied, opened, edited, or revoked. The full URL token is only revealed on demand and is shown once after creation. See the [Profile guide](/guide/using-librislog/profile#urlprofile-sharing) for setup and security details
- 🧺 **Import basket**: search results now offer an **Add to Basket** action next to the existing **Add** button. Collected books appear in a new **Basket** tab with a live count badge, where you can review them, remove individual entries, and import everything in one go. Each entry remembers the reading status, possession status, and medium that were selected when it was added. If some books fail during a basket import, the successful ones are imported and the failed ones stay in the basket so you can retry or remove them. The same book cannot be added twice
- 🔎 **Parallel import searches**: open multiple independent search panels in the Add Book dialog and run different queries concurrently. Each panel keeps its own results and can add selected books to the shared import basket
- 📅 **Configurable reading-date automation**: choose independently whether moving a book to Currently Reading, Read, or Did Not Finish should fill a missing start or finish date automatically. Existing dates are preserved, and disabling automation allows intentionally unknown dates without additional transition popups. See the [Profile guide](/guide/using-librislog/profile#reading-date-automation)
- 📥 **Excel (XLSX) data import**: the Data Import page now accepts `.xlsx` and `.xlsm` workbooks alongside CSV and JSON. LibrisLog reads the workbook's active worksheet, treats the first non-empty row as the header and every following row as a record, shows the parsed sheet name next to the row and field counts, and runs the result through the same mapping, preview, validation, and import flow as CSV. Dates are read as ISO strings, whole numbers stay integers, and empty rows are skipped. See the [Import & Export guide](/guide/using-librislog/import-export#supported-formats)
- 📥 **Bookstats import preset**: a new built-in, read-only mapping for the German Bookstats export. It translates German reading, acquisition, and medium values, converts Excel serial dates, reorders "Last, First" author names, maps the rating (with `0` as unrated), and merges `Genre` and `Kategorie` into tags. Load it from the saved-mappings dropdown like the Goodreads Export preset. See the [Import & Export guide](/guide/using-librislog/import-export#predefined-mappings)

**Bug fixes**
- 🗓️ **Timezone-correct daily page statistics**: pages read between two progress updates are now attributed to calendar days in the user's timezone instead of fixed 24h slots, so the pages-per-day view matches your local days. Your heatmap may shift slightly after the upgrade
- 🕐 **Timezone-aware progress date editing**: editing a progress entry's date in the book detail view now interprets the value in your profile timezone instead of the browser's, so entries stay on the correct calendar day and streaks remain accurate
- 🏷️ **Better contrast for selected suggestion items**: the selected entry in tag and author suggestion dropdowns now has stronger contrast and a visible border in all themes
- ⚠️ **Undated read imports remain usable**: import previews show a non-blocking warning when a book is marked Read without a finish date, instead of treating the intentionally missing date as an import error

**Breaking changes:** None.

[Compare with v1.8.0](https://github.com/codebude/librislog/compare/v1.8.0...v1.9.0)

---

## v1.8.0: Camera & Zoom Control, Optional Telemetry

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-09-02" />

**Summary:** Adds camera selection and zoom control to the barcode scanner, optional anonymous installation telemetry with a publicly verifiable census, a new Homer dashboard integration, and several usability and dependency fixes.

**Features**
- 📷 **Barcode scanner camera & zoom** — switch between your available cameras and zoom in on the code directly in the scan view. Your camera and zoom level are remembered for the next scan
- 📡 **Optional anonymous telemetry** — a privacy-focused installation census (version, OS, architecture, runtime) sent on startup and then every 24 hours. It is enabled by default and can be disabled with `TELEMETRY_DISABLED=true`. The telemetry server is open source and the aggregated results are public at [metrics.librislog.app](https://metrics.librislog.app/). See the [Telemetry guide](/guide/telemetry) for details
- 🖼️ **Homer dashboard integration** — new documentation for showing your reading statistics on a [Homer](https://github.com/bastienwirtz/homer) dashboard using its LibrisLog smart card
- 🔢 **Current-page input clamping** — the page input in the book details now clamps to the book's page count while you type, so an out-of-range value can no longer be entered
- 🔒 **Dependency updates** — upgraded backend and frontend dependencies, including fixes for security advisories in Starlette and joserfc
- 🛠️ **Developer CLI fix** — adjusted the `llc` CLI for the updated Typer exception handling

**Bug fixes**
- 🏷️ Fixed the reading-status badge overflowing its border in the book details view for books with many authors — the author list now wraps and the badge stays on a single line

**Breaking changes:** None.

[Compare with v1.7.0](https://github.com/codebude/librislog/compare/v1.7.0...v1.8.0)

---

## v1.7.0: Reading Streaks & Goals

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-08-26" />

**Summary:** Adds a gamification section to the dashboard with reading streaks and reading goals, a richer book model with multiple authors, a new field-specific search syntax, and a more flexible file import.

**Features**
- 👥 **Multiple authors per book** — a book can have any number of authors (normalized per-user author model). The legacy API `author` field is deprecated in favor of the `authors` list
- 🏆 **Reading streaks & goals** — a gamification section on the dashboard shows your current and all-time longest reading streak (with date range) plus playful progress cards for reading goals. Goals (pages/day, pages/month, books/month, books/year) are configured on the profile page and disabled by default; the whole section can be switched off
- 🎲 **Random "Next to Read" suggestions** — the dashboard's suggestion shelf now picks a random selection from your want-to-read list on every visit
- 🔍 **Enhanced search** — field-specific prefixes (`author:`, `title:`, `publisher:`, `tag:`, `language:`, `possession:`, `notes:`, `description:`), quoted phrases, and `-` negation
- 📚 **"All books" library tab** — browse every book regardless of reading status, with the usual search and sort controls
- 📈 **Author statistics card** — total book count and distinct author count on the statistics page
- 📥 **Improved file import**
  - New `authors` target field (accepts a plain string or an array; legacy `author` mappings keep working)
  - **CSV delimiter** is now user-configurable (default `,`)
  - **`date_added`** can be imported — preserves original library dates when migrating from other tools
  - Transforms may return **lists** for the `authors`/`tags` targets (e.g. `value.split(';')`)
  - Preview renders `authors` and `tags` as JSON arrays
- 📤 **Data export** — `authors` and `tags` export as lists in JSON, round-tripping through the adaptive import
- 🏷️ **Possession naming** — the acquisition/possession field and its search prefix are now consistently called **possession**

**Bug fixes**
- 📊 Fixed the inverted Top Rated / Worst Rated ordering on the statistics page

**Breaking changes**
- ⚠️ Creating a book now requires **at least one author** (via `authors` or the legacy `author` field) — API requests without any author are rejected
- ⚠️ The `availability:` search prefix is renamed to `possession:`

[Compare with v1.6.0](https://github.com/codebude/librislog/compare/v1.6.0...v1.7.0)

---

## v1.6.0: Reading Progress & Possession Tracking

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-08-23" />

**Summary:** Improved reading-progress tracking with automatic cross-view synchronization, a new possession model for tracking what you own, and a wave of UI, statistics, and reliability improvements.

**Features**
- 📖 Automatic synchronization of reading progress across book cards and the detail view
- 📚 Possession tracking — mark books as owned, borrowed, digitally available, or to acquire
- 📊 Possession information added to the statistics page
- 🏷️ Visual "needs to be acquired" indicators on book cards
- 📝 Improved reading-status transitions, including a start-date prompt and smarter progress-completion handling
- 📅 Timezone-aware progress charts with better visualization
- 🎨 Refined sort selector and other UI improvements
- 🔒 Updated dependencies and applied frontend security patches

**Breaking changes:** None.

[Compare with v1.5.2](https://github.com/codebude/librislog/compare/v1.5.2...v1.6.0)

---

## v1.5.2: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-22" />

**Summary:** Small maintenance release improving the accuracy of reading-progress visualizations.

**Bug fixes**
- 📊 Fixed the fallback logic for the start date used in the reading-progress chart in the book detail view
- 🐛 Improved reliability of progress timeline calculations

**Breaking changes:** None.

[Compare with v1.5.1](https://github.com/codebude/librislog/compare/v1.5.1...v1.5.2)

---

## v1.5.1: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-22" />

**Summary:** Small maintenance release fixing an issue in the book edit drawer.

**Bug fixes**
- 🐛 Fixed an issue where the edit drawer could fail to open correctly in certain situations

**Breaking changes:** None.

[Compare with v1.5.0](https://github.com/codebude/librislog/compare/v1.5.0...v1.5.1)

---

## v1.5.0: Password Reset & Usability

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-22" />

**Summary:** Adds password-reset functionality with email support, improves cover imports, and brings several usability and statistics enhancements.

**Features**
- 🔐 Password reset via email
- 🖼️ Cover imports now follow HTTP redirects automatically
- 📱 Android back-button support for navigation drawers
- 💡 Author and publisher suggestions on the Data Hygiene page
- 📊 Reading-progress charts scaled by actual elapsed time

**Bug fixes**
- 🐛 Various UI and usability fixes

**Breaking changes:** None.

[Compare with v1.4.0](https://github.com/codebude/librislog/compare/v1.4.0...v1.5.0)

---

## v1.4.0: Embeddable Views & ARM64

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-14" />

**Summary:** Introduces embeddable library views, ARM64 Docker support, improved data-hygiene workflows, and auto-generated database documentation.

**Features**
- 🖼️ New HTML iframe **embed endpoint** for dashboards, homepages, and other applications
- 🏗️ **ARM64 Docker images** for Raspberry Pi and other ARM-based systems
- 🧹 Improved Data Hygiene UX for incomplete or inconsistent metadata
- 📊 Integration documentation for Dashy and Glance
- 🗄️ Auto-generated database schema documentation
- 🧪 Frontend test and type improvements

**Contributors:** Thank you to **@Jossey28** for adding ARM64 Docker build support.

**Breaking changes:** None.

[Compare with v1.3.1](https://github.com/codebude/librislog/compare/v1.3.1...v1.4.0)

---

## v1.3.1: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-09" />

**Summary:** Small maintenance release improving the reliability of update notifications.

**Bug fixes**
- 🔔 Fixed a caching issue affecting the version update indicator

**Breaking changes:** None.

[Compare with v1.3.0](https://github.com/codebude/librislog/compare/v1.3.0...v1.3.1)

---

## v1.3.0: More Languages

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-09" />

**Summary:** Expands localization support, refines statistics calculations, and improves documentation.

**Features**
- 🌍 Added **Spanish, French, and Chinese (Simplified)** UI languages with expanded localization coverage
- 📈 Improved pages-per-day statistics calculations
- 📖 Integration documentation (Dashy, Home Assistant) and general documentation improvements

**Breaking changes:** None.

[Compare with v1.2.2](https://github.com/codebude/librislog/compare/v1.2.2...v1.3.0)

---

## v1.2.2: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-08" />

**Summary:** Small maintenance release focused on Goodreads import data handling.

**Bug fixes**
- 🐛 Fixed the Goodreads notes transformation during import processing

**Breaking changes:** None.

[Compare with v1.2.1](https://github.com/codebude/librislog/compare/v1.2.1...v1.2.2)

---

## v1.2.1: Import Reliability & Multi-User Consistency

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-08" />

**Summary:** Focused on import reliability, multi-user data consistency, and quality-of-life improvements.

**Features**
- 📥 Improved Goodreads import mapping templates and book import handling
- 👥 **Per-user ISBN uniqueness** — the same ISBN can now exist for different users without conflict
- 🌐 Support for a custom documentation domain

**Bug fixes**
- 🐛 Fixed issues affecting Goodreads imports

**Contributors:** Thank you to **@badcrc** for their first contribution.

**Breaking changes:** None. (The ISBN uniqueness change is a database migration and runs automatically on upgrade.)

[Compare with v1.2.0](https://github.com/codebude/librislog/compare/v1.2.0...v1.2.1)

---

## v1.2.0: Startup Screen & Update Checks

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-01" />

**Summary:** Improves the initial user experience and adds automatic update awareness.

**Features**
- 🚀 New startup loading screen for a smoother launch
- 🔔 **Release update check** that notifies you when a new version is available

**Breaking changes:** None.

[Compare with v1.1.1](https://github.com/codebude/librislog/compare/v1.1.1...v1.2.0)

---

## v1.1.1: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-01" />

**Summary:** Maintenance release focused on thumbnails, bug fixes, and stability.

**Bug fixes**
- 🖼️ Improved thumbnail generation and image quality
- 🐛 Fixed several cover and thumbnail handling issues
- 🧪 Test-suite maintenance and documentation build workflow improvements

**Breaking changes:** None.

[Compare with v1.1.0](https://github.com/codebude/librislog/compare/v1.1.0...v1.1.1)

---

## v1.1.0: Polish & Missing Covers

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-05-31" />

**Summary:** A refinement release focused on usability, workflow completeness, and overall polish.

**Features**
- 📚 Improved missing-book-cover workflow for incomplete metadata
- 🌐 Refined translations and i18n coverage
- 🧩 UX and UI improvements across the application
- 📖 Documentation updates

**Breaking changes:** None.

[Compare with v1.0.0](https://github.com/codebude/librislog/compare/v1.0.0...v1.1.0)

---

## v1.0.0: Initial Release

<Badge type="tip" text="Initial release" /> <Badge type="info" text="2026-05-28" />

**Summary:** The first stable release of LibrisLog — a self-hosted, multi-user book tracking web app with full data ownership.

**Features**
- 📚 Library management with four reading states (Want to Read, Reading, Read, Did Not Finish)
- 📖 Reading-progress tracking with per-book history
- 📊 Statistics dashboard (heatmaps, charts, reading trends)
- 📷 ISBN barcode scanning (browser-based, mobile-friendly)
- 📥 Imports from Goodreads, Open Library, Google Books, and custom CSV/JSON
- 🖼️ Automatic cover-art fetching with manual fallback
- 👥 Multi-user support with roles and optional OIDC login
- 🔌 REST API with OpenAPI documentation
- 🐳 Self-hosted via Docker Compose (SQLite, lightweight setup)
- 🎨 Light/dark themes and responsive UI

[Full changelog](https://github.com/codebude/librislog/commits/v1.0.0)

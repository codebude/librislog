# Release Notes

All LibrisLog releases, newest first — what's new, what was fixed, and anything you need to know before upgrading.

> **Upgrading:** releases are backwards compatible. Database migrations run automatically when the container starts (`alembic upgrade head`), so upgrading is a drop-in replacement. We always recommend [taking a backup](/guide/using-librislog/administration#backup-restore) before an upgrade.

You can also browse the [GitHub Releases](https://github.com/codebude/librislog/releases) page and the [full changelog](https://github.com/codebude/librislog/commits/main).

## Latest Release

::: tip ⭐ v1.8.0 — Camera & Zoom Control, Optional Telemetry
LibrisLog v1.8.0 brings camera selection and zoom control to the barcode scanner, optional anonymous installation telemetry with a publicly verifiable census, a new Homer dashboard integration, and several usability and dependency fixes.
:::

### All releases

| Version | Date | Type |
|---|---|---|
| [v1.9.0](#v1-9-0-smarter-import-search-input-ux) | Unreleased | Feature release |
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

## v1.9.0: Smarter Import Search & Input UX

<Badge type="warning" text="Unreleased" /> <Badge type="tip" text="Feature release" />

**Summary:** Adds shareable read-only public profile pages with configurable access and content, groups duplicate import-search results into expandable edition groups, lets you collect search results in an import basket and import them all at once, makes running searches cancelable, introduces an adaptive date input with a native picker, adds optional book media and medium statistics, supports localized medium and possession searches, detects insecure camera contexts, and fixes timezone handling in the daily page statistics and progress log editing.

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

**Bug fixes**
- 🗓️ **Timezone-correct daily page statistics**: pages read between two progress updates are now attributed to calendar days in the user's timezone instead of fixed 24h slots, so the pages-per-day view matches your local days. Your heatmap may shift slightly after the upgrade
- 🕐 **Timezone-aware progress date editing**: editing a progress entry's date in the book detail view now interprets the value in your profile timezone instead of the browser's, so entries stay on the correct calendar day and streaks remain accurate
- 🏷️ **Better contrast for selected suggestion items**: the selected entry in tag and author suggestion dropdowns now has stronger contrast and a visible border in all themes

**Breaking changes:** None.

[Compare with v1.8.0](https://github.com/codebude/librislog/compare/v1.8.0...main)

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

[Compare with v1.7.0](https://github.com/codebude/librislog/compare/v1.7.0...main)

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

[Compare with v1.6.0](https://github.com/codebude/librislog/compare/v1.6.0...main)

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

[Full changelog](https://github.com/codebude/librislog/compare/v1.5.2...v1.6.0)

---

## v1.5.2: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-22" />

**Summary:** Small maintenance release improving the accuracy of reading-progress visualizations.

**Bug fixes**
- 📊 Fixed the fallback logic for the start date used in the reading-progress chart in the book detail view
- 🐛 Improved reliability of progress timeline calculations

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.5.1...v1.5.2)

---

## v1.5.1: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-22" />

**Summary:** Small maintenance release fixing an issue in the book edit drawer.

**Bug fixes**
- 🐛 Fixed an issue where the edit drawer could fail to open correctly in certain situations

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.5.0...v1.5.1)

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

[Full changelog](https://github.com/codebude/librislog/compare/v1.4.0...v1.5.0)

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

[Full changelog](https://github.com/codebude/librislog/compare/v1.3.1...v1.4.0)

---

## v1.3.1: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-09" />

**Summary:** Small maintenance release improving the reliability of update notifications.

**Bug fixes**
- 🔔 Fixed a caching issue affecting the version update indicator

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.3.0...v1.3.1)

---

## v1.3.0: More Languages

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-09" />

**Summary:** Expands localization support, refines statistics calculations, and improves documentation.

**Features**
- 🌍 Added **Spanish, French, and Chinese (Simplified)** UI languages with expanded localization coverage
- 📈 Improved pages-per-day statistics calculations
- 📖 Integration documentation (Dashy, Home Assistant) and general documentation improvements

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.2.2...v1.3.0)

---

## v1.2.2: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-08" />

**Summary:** Small maintenance release focused on Goodreads import data handling.

**Bug fixes**
- 🐛 Fixed the Goodreads notes transformation during import processing

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.2.1...v1.2.2)

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

[Full changelog](https://github.com/codebude/librislog/compare/v1.2.0...v1.2.1)

---

## v1.2.0: Startup Screen & Update Checks

<Badge type="tip" text="Feature release" /> <Badge type="info" text="2026-06-01" />

**Summary:** Improves the initial user experience and adds automatic update awareness.

**Features**
- 🚀 New startup loading screen for a smoother launch
- 🔔 **Release update check** that notifies you when a new version is available

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.1.1...v1.2.0)

---

## v1.1.1: Maintenance

<Badge type="info" text="Maintenance" /> <Badge type="info" text="2026-06-01" />

**Summary:** Maintenance release focused on thumbnails, bug fixes, and stability.

**Bug fixes**
- 🖼️ Improved thumbnail generation and image quality
- 🐛 Fixed several cover and thumbnail handling issues
- 🧪 Test-suite maintenance and documentation build workflow improvements

**Breaking changes:** None.

[Full changelog](https://github.com/codebude/librislog/compare/v1.1.0...v1.1.1)

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

[Full changelog](https://github.com/codebude/librislog/compare/v1.0.0...v1.1.0)

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

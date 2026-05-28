# About LibrisLog

LibrisLog is a **multi-user book tracking web application** designed for readers who want to organize their library, track reading progress, and gain insights into their reading habits.

## Features

- **Library Management**: Organize books into four reading statuses — Want to Read, Currently Reading, Read, and Did Not Finish
- **Book Import**: Search Open Library, Google Books, and Hardcover.app. Scan ISBN barcodes for quick lookup
- **Reading Progress**: Track pages read over time with a visual timeline and calendar heatmap
- **Statistics Dashboard**: Charts showing pages read per month, books finished, language distribution, and more
- **Cover Management**: Automatic cover image scraping from multiple sources with manual override
- **Data Portability**: Export/import library as JSON or CSV. Full backup and restore functionality
- **REST API**: Full API with OpenAPI documentation for programmatic access
- **Multilingual**: English and German UI support
- **Themes**: Light, dark, and custom DaisyUI themes with persistent preferences

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Svelte 5 + SvelteKit + Tailwind CSS 4 + DaisyUI 5 |
| Backend | FastAPI + SQLModel + Alembic + Pydantic v2 |
| Database | SQLite |
| Search Sources | Open Library, Google Books, Hardcover.app, AbeBooks, Amazon |
| Charts | Chart.js + chartjs-chart-matrix + chartjs-plugin-zoom |
| Icons | Lucide Svelte |
| Scraping | curl-cffi + Scrapling + BrowserForge |
| Auth | Session cookies, optional OIDC (Authlib) |
| Barcode | html5-qrcode |
| Dates | dayjs |
| Misc | cachetools, cryptography, restrictedpython, pycountry, passlib, hammerjs |
| Docs | VitePress + viewerjs |
| CI/Tests | pytest (backend), Vitest (frontend), Playwright (E2E) |

## Author

Created and maintained by [Raffael Herrmann](https://github.com/codebude).

## License

Released under the MIT License.
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
| Frontend | SvelteKit + DaisyUI + Tailwind CSS |
| Backend | FastAPI + SQLModel + Alembic |
| Database | SQLite |
| Search | Open Library, Google Books, Hardcover.app |
| Charts | Chart.js |
| Icons | Lucide |

## Author

Created and maintained by [Raffael Herrmann](https://github.com/codebude).

## License

Released under the MIT License.
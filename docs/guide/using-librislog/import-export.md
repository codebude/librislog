# Import & Export

LibrisLog provides multiple ways to get data in and out of the system, ensuring your library is always portable.

## Book Import

### Search Import

The most common way to add books is by searching external sources:

1. Click "Add Book" in the library
2. Enter a title, author, or ISBN in the search box
3. The app queries:
   - **Open Library** (always, no key required)
   - **Google Books** (if `GOOGLE_BOOKS_API_KEY` is set)
   - **Hardcover.app** (if `HARDCOVER_APP_API_TOKEN` is set)
4. Select a result to import with full metadata and cover

### ISBN Barcode Scan

On mobile devices:
1. Tap the scan button in the import dialog
2. Point the camera at an ISBN barcode
3. The app detects the barcode and searches automatically

### Manual Entry

If no search results are found, enter book details manually. All fields are optional except title.

## Data Export

Export your entire library or subsets of data:

### Export Formats

| Format | Description |
|--------|-------------|
| **JSON** | Complete data with all metadata and relationships |
| **CSV** | Tabular format, one row per book |
| **ZIP** | Combined JSON + cover images |

### Export Datasets

Choose which data to include:
- Books (full metadata)
- Reading progress entries
- Tags
- Cover images

### Export Process

1. Go to the Data page
2. Select datasets and format
3. Click Export
4. Download the generated file

## Data Import

Import data from external sources:

![Data Import](/screenshots/data-import.png)

### Supported Formats

- **JSON** — LibrisLog export format
- **CSV** — Custom field mapping supported

### Field Mapping

When importing CSV, map source columns to LibrisLog fields:
- Source field dropdown shows all columns from the CSV
- Target field shows available LibrisLog properties
- Optional transform expressions (Python) for data conversion

### Transform DSL

Per-field Python expressions allow data transformation:
```python
# Examples:
value.upper()              # Convert to uppercase
str(int(value))            # Convert to integer then back to string
"https://example.com/" + value  # Prefix a URL
```

Available variables:
- `value` — The field value
- `row` — The entire row as a dictionary
- `context` — Import context (not commonly used)

### Predefined Mappings

Common import formats have predefined mappings:
- **Goodreads Export** — Maps Goodreads CSV columns automatically

### Validation

Before importing:
1. Parse and preview the data
2. Review transformed rows
3. Check for errors
4. Validate the full dataset

The import process shows progress with a count of imported and failed rows.

## Backup & Restore

### Full Backup

Create a complete backup of the database:
1. Go to Admin → Backup
2. Click "Create Backup"
3. Download the `.db` file

### Restore

Restore from a backup:
1. Go to Admin → Restore
2. Upload a `.db` backup file
3. The app validates the backup before restoring
4. Current data is replaced with backup data

::: warning
Restore overwrites all current data. Create a backup first if you want to preserve your current library.
:::

## API Access

For programmatic import/export, use the REST API. See the [API documentation](../../api/) for details.
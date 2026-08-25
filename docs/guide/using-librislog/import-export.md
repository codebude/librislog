# Import & Export

LibrisLog provides multiple ways to get data in and out of the system, ensuring your library is always portable.

## Book Import

### Search Import

The most common way to add books is by searching external sources:

1. Click "Add Book" in the library
2. Enter a title, author, or ISBN in the search box
3. The app queries:
   - **Open Library** (always, no key required)
   - **Google Books** (if `GOOGLE_BOOKS_API_KEY` is set — see [API Keys](/guide/api-keys))
   - **Hardcover.app** (if `HARDCOVER_APP_API_TOKEN` is set — see [API Keys](/guide/api-keys))
4. Select a result to import with full metadata and cover
5. Choose an availability value (owned, borrowed, digital access, or to acquire) before saving

### ISBN Barcode Scan

On mobile devices:
1. Tap the scan button in the import dialog
2. Point the camera at an ISBN barcode
3. The app detects the barcode and searches automatically
4. Pick the search result and select an availability value before saving

### Manual Entry

If no search results are found, enter book details manually. Title, author, page count, and availability are required; all other fields are optional.

Authors can be added as multiple values: type a name and press **Enter** (or pick a suggestion) to add a chip. A book can have any number of authors. Commas inside an author name (e.g. `Asimov, Isaac`) are preserved — they are not treated as separators.

### Search Import

When a search source returns multiple authors for a book (e.g. Open Library, Google Books, or Hardcover), the app keeps them as a list and creates one author per entry. Sources that return a single combined string are split only on `;`, ` & `, or ` and ` — never on commas.

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

The JSON export mirrors the API shape: `author` is the joined string (separated with `; `), `authors` is the list of names, and `tags` is a list of tag names. All three round-trip through the adaptive import.

### Field Mapping

When importing CSV, map source columns to LibrisLog fields:
- Source field dropdown shows all columns from the CSV
- Target field shows available LibrisLog properties
- Optional transform expressions (Python) for data conversion

`acquisition_status` is required for imports. Map it to one of `owned`, `borrowed`, `digital_access`, or `to_acquire`; use a transform when the source file uses different names.

#### Authors are adaptive

The import target field is **`authors`**. Its source value adapts:

- **Array value** (e.g. a JSON `authors` list) → each array entry becomes a separate author.
- **String value** (e.g. a CSV cell) → normally becomes **one** author, and commas inside the name are preserved, so `"Asimov, Isaac"` stays a single author. To encode several authors in a single cell, separate them with `;`, ` & `, or ` and ` (e.g. `"Frank Herbert; Brian Herbert"`). This is how the CSV export writes the dedicated `authors` column, so exports round-trip losslessly.

The import preview shows how each row's author value will be interpreted before you import.

The `tags` field is adaptive too: a JSON `tags` array contributes one tag per entry, while a comma-separated string (CSV) is split on commas.

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

Backup and restore are admin-only features. See [Administration](./administration) for details.

## API Access

For programmatic import/export, use the REST API. See the [API documentation](../../api/) for details.

# Data Hygiene

The Data Hygiene page helps you find and fix books with missing metadata. It's accessible from your **Profile → Manage my data → Data Hygiene**.

## Attribute Filtering

The page lists books that are missing one or more of the tracked attributes. Use the chip buttons at the top to filter by specific attributes:

- **Single attribute**: Click a chip to show only books missing that specific field
- **Multiple attributes**: Click several chips to narrow down further
- **Match mode**: Toggle between "Match any" (OR logic — book missing any selected attribute) and "Match all" (AND logic — book must miss all selected attributes)
- **Default view**: With no chips selected, all books missing at least one tracked attribute are shown

Tracked attributes: title, author, ISBN, publisher, published year, blurb, language, subtitle, page count, and cover.

## Reviewing Missing Data

Each row in the table shows:
- Book title, author, ISBN, and publisher
- A "Missing" column with badges for each missing attribute

Select individual books or use the checkbox in the header to select all visible books. The action bar at the bottom appears once at least one book is selected.

## Batch Editing

The batch action bar lets you update multiple books at once:

1. **Select books** using the checkboxes
2. **Pick a field** from the dropdown (only attributes that are missing in the selected books appear)
3. **Enter a value** — text fields get a text input, numeric fields (page count, year) get a number input
4. **Click "Apply to selected"** to open a confirmation dialog showing a preview of affected books
5. **Confirm** to apply the change

### Cover URL

When setting `cover_url`, the app validates the URL, downloads the image, and stores it locally. If the download fails, that book is skipped and reported in the result summary.

### Language

Language values are normalized to uppercase; invalid ISO codes are rejected.

### Published Year

No lower bound is enforced, so ancient or religious texts (e.g., the Bible) can be entered with years before 1000.

## Success & Error States

- **All complete**: When no books are missing data, a green success message appears
- **Filtered complete**: When specific attributes are selected and all books have them, a tailored success message is shown
- **Errors**: API errors are displayed in an alert banner; dismiss it to try again

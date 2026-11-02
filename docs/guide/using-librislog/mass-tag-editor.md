# Mass Tag Editor

The Mass Tag Editor lets you add or remove tags on many books at once. It is accessible from **Profile → Manage my data → Mass Tag Editor**.

Tags are the recommended way to group books (for example a shelf, a series, or a reading project). This page makes applying them to a large library practical.

## Filtering books

Use the filter bar to narrow the list:

- **Search** — full text search, including field prefixes such as `tag:cars` or `author:"Jane Driver"` and negation with `-`.
- **Reading status**, **Medium**, **Acquisition status** — standard library filters.
- **Tag** — show only books that have (or lack) a specific tag, using the **Has tag** / **Lacks tag** toggle.

The table shows the title, author, current tags, and reading status of each book. Click a title to open it in the library.

## Selecting books

- Check individual rows, or use the header checkbox to select all books on the current page.
- **Load more** appends the next page without losing your selection.
- **Select all N matching** (shown when more than one page exists) selects every book that matches the current filters, even those not yet loaded. The action bar then shows the total count.
- **Clear selection** leaves the all-matching mode.

Up to 500 books are processed per request; larger selections are split automatically and progress is shown.

## Adding and removing tags

The action bar at the bottom of the screen has two fields:

- **Add tags** — tags to apply to every selected book.
- **Remove tags** — tags to remove from every selected book.

A tag cannot be both added and removed in the same operation. Suggestions come from your existing tags.

### Case differences

Tag matching is exact, including capitalization. If you type a tag that differs only in capitalization from an existing tag (for example `sci-fi` next to `Sci-Fi`), a warning appears with a one-click shortcut to reuse the existing spelling. The warning is advisory; the tag you typed is still created if you proceed.

## Confirmation and result

Click **Apply to selected** to open a confirmation dialog showing the affected count, the tags to add and remove, and a preview of the first ten affected titles (or a summary when all matching books are selected). Confirm to apply.

After a successful run, a summary toast reports how many books changed, how many tag links were added and removed, and which tags were deleted because they no longer had any book.

## Orphan tag cleanup

When a tag ends up on no book after a removal, it is deleted automatically, the same as when editing a single book or deleting one.

## Limits

- At most 500 books per request; larger selections are chunked automatically.
- At most 50 tags per add or remove list.
- Tag names must not contain commas.

## See also

- [Data Hygiene](/guide/using-librislog/data-hygiene) — bulk-fix missing metadata.
- [Library](/guide/using-librislog/library) — search and filter syntax, including `tag:`.
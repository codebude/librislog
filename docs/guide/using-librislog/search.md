# Search

The search box on the **Dashboard**, **Library**, and dedicated `/search` page supports plain-text matching as well as field-specific and negated queries.

## Field prefixes

Use `<field>:<value>` to search in a single field. The field prefixes are always in **English**, regardless of the UI language.

| Prefix | Field | Example |
|--------|-------|---------|
| `author` | Author(s) | `author:Murakami` |
| `title` | Title | `title:"The Hobbit"` |
| `publisher` | Publisher | `publisher:Penguin` |
| `language` | Language | `language:Japanese` |
| `tag` | Tag name | `tag:fantasy` |
| `possession` | Possession status | `possession:owned` |
| `notes` | Private notes | `notes:"to reread"` |
| `description` | Blurb / description | `description:"middle earth"` |

Use quotes for values that contain spaces: `title:"The Silmarillion"`.

The `author:` prefix matches **any** author assigned to a book — a book with multiple authors matches if any of them contains the search value.

### Possession values

The `possession` prefix matches the exact possession status. Accepted values include:

- `to_acquire` (or `to acquire`)
- `owned`
- `borrowed`
- `digital`

Example: `possession:"to acquire"` shows books you want to buy.

## Negation

Prefix a term with `-` to exclude matches.

- `-author:Rowling`
- `-tag:horror`
- `Haushofer -"Die Wand"`

## Combining terms

Separate terms with spaces. All terms are combined with **AND**.

- `author:Murakami -title:Norwegian` — Murakami books except those whose title contains "Norwegian"
- `tag:fantasy possession:owned` — owned fantasy books

## Plain text

An unprefixed phrase searches across title, author, publisher, language, notes, description, and tags. It is matched as a phrase, not as individual words.

- `Marlen Haushofer` — matches the exact phrase across the supported fields
- `Haushofer -Wand` — matches "Haushofer" but excludes books whose fields contain "Wand"

## Quick reference in the app

Click the **?** icon next to any search input to open a quick-reference card with the available prefixes and examples.

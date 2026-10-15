# API Keys

Some external sources require API keys. All are optional: Open Library, BnF, Inventaire.io, the Library of Congress, and the German National Library need no key at all, so LibrisLog works out of the box.

Sources without a key can be switched off individually, see [Configuration](/guide/configuration).

::: warning Both keyed sources are off in `.env.example`
A key alone is not enough to make a source answer, and leaving a source switched on
without its key is just noise. `.env.example` therefore ships
`HARDCOVER_IMPORT_SEARCH_ENABLED=false` and `GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=false`.
Set the credential and flip the matching switch to `true`:

```bash
GOOGLE_BOOKS_API_KEY=your-key
GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=true
```

```bash
HARDCOVER_APP_API_TOKEN=your-token
HARDCOVER_IMPORT_SEARCH_ENABLED=true
```

The built-in default for both switches is `true`, so an existing `.env` that does not
mention them keeps working after an upgrade. If you leave a source on without its
credential, it is listed in the search progress as skipped and no request is sent.
:::

## Google Books API

Enables Google Books as a fallback search source and improves cover resolution. Remember to also set `GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=true`.

1. Go to the [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Library**
4. Search for "Books API" and enable it
5. Go to **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **API Key**
7. Copy the key and set it as `GOOGLE_BOOKS_API_KEY` in your `.env`

> **Note**: Google Books API has usage limits. For most personal use, the free tier is sufficient. See [Google's documentation](https://developers.google.com/books) for quota details.

## Hardcover API

Enables Hardcover.app as an additional search source. Remember to also set `HARDCOVER_IMPORT_SEARCH_ENABLED=true`.

1. Sign in to [hardcover.app](https://hardcover.app)
2. Go to your profile → **Settings** → **API**
3. Create a new API token
4. Copy the token and set it as `HARDCOVER_APP_API_TOKEN` in your `.env`

# API Keys

Some external sources require API keys. All are optional — LibrisLog works out of the box with Open Library.

## Google Books API

Enables Google Books as a fallback search source and improves cover resolution.

1. Go to the [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Library**
4. Search for "Books API" and enable it
5. Go to **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **API Key**
7. Copy the key and set it as `GOOGLE_BOOKS_API_KEY` in your `.env`

> **Note**: Google Books API has usage limits. For most personal use, the free tier is sufficient. See [Google's documentation](https://developers.google.com/books) for quota details.

## Hardcover API

Enables Hardcover.app as an additional search source.

1. Sign in to [hardcover.app](https://hardcover.app)
2. Go to your profile → **Settings** → **API**
3. Create a new API token
4. Copy the token and set it as `HARDCOVER_APP_API_TOKEN` in your `.env`

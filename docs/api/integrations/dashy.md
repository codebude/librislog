# Dashy

LibrisLog can be integrated into [Dashy](https://dashy.to/), a self-hosted
dashboard for your services, using its
[HTML embedded widget](https://dashy.to/docs/widgets#html-embedded-widget).

This widget displays your reading statistics as styled stat cards directly on
your Dashy dashboard.

## Prerequisites

- A running LibrisLog instance reachable from your Dashy server
- An [API key](/api/integrations/#api-keys) with access to the
  statistics endpoint
- **CORS must be configured** — add your Dashy URL to the
  [`CORS_ORIGINS`](/guide/configuration#core-settings) environment variable
  of the LibrisLog backend so that the browser can fetch the API directly

## Configuration

Add the following to the Dashy `conf.yml` under the section or item where you
want the widget to appear:

```yaml
widgets:
  - type: embed
    updateInterval: 300
    options:
      html: |
        <div class="librislog-widget">
          <div class="ll-stat-item">
            <span class="ll-label">Reading</span>
            <span class="ll-value" id="ll-reading">-</span>
          </div>
          <div class="ll-stat-item">
            <span class="ll-label">Read</span>
            <span class="ll-value" id="ll-read">-</span>
          </div>
          <div class="ll-stat-item">
            <span class="ll-label">Want to Read</span>
            <span class="ll-value" id="ll-wtr">-</span>
          </div>
          <div class="ll-stat-item">
            <span class="ll-label">Total Books</span>
            <span class="ll-value" id="ll-total">-</span>
          </div>
        </div>
      css: |
        .librislog-widget {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 0.75rem;
          padding: 0.5rem;
          font-family: inherit;
        }
        .ll-stat-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          background: var(--background-elevated, rgba(255,255,255,0.05));
          border: 1px solid var(--outline-color, rgba(255,255,255,0.1));
          border-radius: 6px;
          padding: 0.5rem;
          text-align: center;
        }
        .ll-label {
          font-size: 0.8rem;
          opacity: 0.7;
          color: var(--text-color, #fff);
          margin-bottom: 0.25rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .ll-value {
          font-size: 1.4rem;
          font-weight: bold;
          color: var(--primary, #00bc8c);
        }
      script: |
        (async function() {
          const apiUrl = '<LIBRISLOG-URL>/api/books/stats';
          const apiKey = '<API-KEY>';

          try {
            const response = await fetch(apiUrl, {
              method: 'GET',
              headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
              }
            });

            if (!response.ok) throw new Error('API request failed');

            const data = await response.json();

            document.getElementById('ll-reading').innerText = data.books_currently_reading ?? data.books_reading ?? 0;
            document.getElementById('ll-read').innerText = data.books_read ?? 0;
            document.getElementById('ll-wtr').innerText = data.books_want_to_read ?? 0;
            document.getElementById('ll-total').innerText = data.total_books ?? 0;

          } catch (error) {
            console.error('LibrisLog Widget Error:', error);
            const elements = ['ll-reading', 'll-read', 'll-wtr', 'll-total'];
            elements.forEach(id => {
              const el = document.getElementById(id);
              if (el) el.innerText = '!';
              if (el) el.style.color = 'var(--danger, #ff0033)';
            });
          }
        })();
```

Replace the placeholders with your own values:

| Placeholder | Example | Description |
|---|---|---|
| `<LIBRISLOG-URL>` | `http://192.168.1.100:8000` | The base URL of your LibrisLog instance (http or https) |
| `<API-KEY>` | `lk_nRHsF3jxIBDa9u....` | An API key with access to the statistics endpoint |

The `updateInterval` is specified in seconds. `300` equals 5 minutes.

## CORS

Since the widget runs inside the Dashy iframe and fetches the LibrisLog API
directly from the browser, you must add your Dashy URL to the
[`CORS_ORIGINS`](/guide/configuration#core-settings) environment variable of
the LibrisLog backend. For example:

```
CORS_ORIGINS=["https://dashy.YOUR-DOMAIN"]
```

## Result

![Dashy Widget](/screenshots/integrations-dashy.png)

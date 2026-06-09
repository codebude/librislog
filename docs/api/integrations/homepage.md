# Homepage

LibrisLog can be integrated into [Homepage](https://gethomepage.dev/), a
modern dashboard for your self-hosted services, using its
[custom API widget](https://gethomepage.dev/widgets/services/customapi/).

This widget displays your reading statistics directly on your Homepage
dashboard.

## Prerequisites

- A running LibrisLog instance reachable from your Homepage server
- An [API key](/api/integrations/#api-keys) with access to the
  statistics endpoint

## Configuration

Add the following entry to your Homepage `services.yaml`:

```yaml
- librislog:
    icon: mdi-book-heart
    href: <LIBRISLOG-URL>
    siteMonitor: <LIBRISLOG-URL>
    widget:
        type: customapi
        url: <LIBRISLOG-URL>/api/books/stats
        method: GET
        headers:
            X-API-Key: "<API-KEY>"
        refreshInterval: 300000
        display: block
        mappings:
            - field: books_read
              label: Read
              format: number
            - field: books_reading
              label: Reading
              format: number
            - field: books_want_to_read
              label: Want to read
              format: number
            - field: total_books
              label: Total
              format: number
```

Replace the placeholders with your own values:

| Placeholder | Example | Description |
|---|---|---|
| `<LIBRISLOG-URL>` | `http://192.168.1.100:8000` | The base URL of your LibrisLog instance (http or https) |
| `<API-KEY>` | `lk_nRHsF3jxIBDa9u....` | An API key with access to the statistics endpoint |

The `refreshInterval` is specified in milliseconds. `300000` ms equals 5
minutes.

## Result

![Homepage Widget](/screenshots/integrations-homepage.png)

# Glance

LibrisLog can be integrated into [Glance](https://github.com/glanceapp/glance),
a self-hosted dashboard for your services, using its
[custom API widget](https://github.com/glanceapp/glance/blob/main/docs/custom-api.md).

This widget displays your reading statistics as styled stat cards directly on
your Glance dashboard.

## Prerequisites

- A running LibrisLog instance reachable from your Glance server
- An [API key](/api/integrations/#api-keys) with access to the
  statistics endpoint

## Configuration

Add the following to your Glance `glance.yml` under the widget section:

```yaml
widgets:
  - type: custom-api
    title: LibrisLog stats
    cache: 1h
    url: <LIBRISLOG-URL>/api/books/stats
    headers:
      x-api-key: <API-KEY>
      Accept: application/json
    template: |
      <div class="flex justify-between text-center">
        <div>
          <div class="color-highlight size-h3">{{ .JSON.Int "books_read" | formatNumber }}</div>
          <div class="size-h6">READ</div>
        </div>
        <div>
          <div class="color-highlight size-h3">{{ .JSON.Int "books_reading" | formatNumber }}</div>
          <div class="size-h6">READING</div>
        </div>
        <div>
          <div class="color-highlight size-h3">{{ .JSON.Int "books_want_to_read" | formatNumber }}</div>
          <div class="size-h6">WANT TO READ</div>
        </div>
        <div>
          <div class="color-highlight size-h3">{{ .JSON.Int "total_books" | formatNumber }}</div>
          <div class="size-h6">TOTAL</div>
        </div>
      </div>
```

Replace the placeholders with your own values:

| Placeholder | Example | Description |
|---|---|---|
| `<LIBRISLOG-URL>` | `http://192.168.1.100:8000` | The base URL of your LibrisLog instance (http or https) |
| `<API-KEY>` | `lk_nRHsF3jxIBDa9u....` | An API key with access to the statistics endpoint |

## Result

![Glance Widget (dark)](/screenshots/integrations-glance.png)

![Glance Widget (light)](/screenshots/integrations-glance-light.png)

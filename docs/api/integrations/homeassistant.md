# Home Assistant

LibrisLog can be integrated into [Home Assistant](https://www.home-assistant.io/),
a popular open-source home automation platform, using its
[RESTful integration](https://www.home-assistant.io/integrations/rest/).

This integration creates sensors that expose your LibrisLog reading statistics
directly in Home Assistant.

## Prerequisites

- A running LibrisLog instance reachable from your Home Assistant server
- An [API key](/api/integrations/#api-keys) with access to the
  statistics endpoint

## Configuration

Add the following to your Home Assistant `configuration.yaml`:

```yaml
rest:
  - resource: <LIBRISLOG-URL>/api/books/stats
    method: GET
    headers:
      X-API-Key: "<API-KEY>"
      Content-Type: application/json
    scan_interval: 300
    sensor:
      - name: "Total Books"
        unique_id: librislog_total_books
        value_template: "{{ value_json.total_books }}"
        icon: mdi:bookshelf
        unit_of_measurement: "Books"
      - name: "Books Read"
        unique_id: librislog_books_read
        value_template: "{{ value_json.books_read }}"
        icon: mdi:book-check
        unit_of_measurement: "Books"
      - name: "Books Currently Reading"
        unique_id: librislog_books_currently_reading
        value_template: "{{ value_json.books_reading }}"
        icon: mdi:book-open-page-variant
        unit_of_measurement: "Books"
      - name: "Want to Read"
        unique_id: librislog_books_want_to_read
        value_template: "{{ value_json.books_want_to_read }}"
        icon: mdi:bookmark-plus
        unit_of_measurement: "Books"

  - resource: <LIBRISLOG-URL>/api/statistics
    method: GET
    headers:
      X-API-Key: "<API-KEY>"
      Content-Type: application/json
    scan_interval: 600
    sensor:
      - name: "Average Rating"
        unique_id: librislog_average_rating
        value_template: "{{ value_json.average_rating | round(2) if value_json.average_rating is not none else 'N/A' }}"
        icon: mdi:star
        unit_of_measurement: "★"
      - name: "Average Page Count"
        unique_id: librislog_average_page_count
        value_template: "{{ value_json.avg_page_count | round(0) if value_json.avg_page_count is not none else 'N/A' }}"
        icon: mdi:file-document-multiple
        unit_of_measurement: "Pages"
```

Replace the placeholders with your own values:

| Placeholder | Example | Description |
|---|---|---|
| `<LIBRISLOG-URL>` | `http://192.168.1.100:8000` | The base URL of your LibrisLog instance (http or https) |
| `<API-KEY>` | `lk_nRHsF3jxIBDa9u....` | An API key with access to the statistics endpoint |

The `scan_interval` is specified in seconds. The first resource polls every
5 minutes, the second every 10 minutes.

## Result

![Home Assistant Sensors - Part 1](/screenshots/integrations-homeassistant-1.png)

![Home Assistant Sensors - Part 2](/screenshots/integrations-homeassistant-2.png)

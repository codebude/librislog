# Integrations

LibrisLog exposes a full REST API that third-party applications can use to
display your reading data, automate workflows, or build custom dashboards.

All integrations below are backed by the LibrisLog API. You will need an
API key to use them. You can create one either:

<span id="api-keys"></span>

- **Via the web UI** — go to your [Profile](/api/#creating-an-api-key)
  page and click "Create API Key".
- **Via the API** — see the
  [Headless Setup](/api/setup#3-create-an-api-key) guide for a
  CLI-based workflow.

## Embed Widgets (No Header Auth)

Some dashboards only support iframe widgets and cannot set custom HTTP
headers. For these integrations you need an **embed token**, used with the
[Embed API](/api/integrations/embed-api):

<span id="embed-tokens"></span>

- **Create one** from your [Profile page](/guide/using-librislog/profile) under
  "Embed Tokens".
- Embed tokens are **scoped to embed endpoints only** and can be revoked
  or rotated independently of API keys.
- They are passed as query parameter (`?token=...`) in the widget URL.

## Available Integrations

- [Embed API](/api/integrations/embed-api) — Generic embed widget API for
  iframe-based dashboards. Uses scoped embed tokens and supports custom
  styling.
- [Dashy](/api/integrations/dashy) — Display your LibrisLog statistics as
  styled stat cards on a [Dashy](https://dashy.to/) dashboard using the HTML
  embedded widget.
- [Glance](/api/integrations/glance) — Display your LibrisLog statistics on a
  [Glance](https://github.com/glanceapp/glance) dashboard using the custom API
  widget.
- [Home Assistant](/api/integrations/homeassistant) — Expose your LibrisLog
  reading statistics as sensors in
  [Home Assistant](https://www.home-assistant.io/) using the RESTful
  integration.
- [Homarr](/api/integrations/homarr) — Display your LibrisLog statistics on a
  [Homarr](https://homarr.dev/) dashboard using the iframe widget.
- [Homepage](/api/integrations/homepage) — Display your LibrisLog statistics
  on a [Homepage](https://gethomepage.dev/) dashboard using the custom API
  widget.

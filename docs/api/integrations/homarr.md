# Homarr

LibrisLog can be integrated into [Homarr](https://homarr.dev/), a modern
dashboard for your self-hosted services, using its
[iframe widget](https://homarr.dev/docs/widgets/iframe/).

This displays your reading statistics as a self-contained stats card on your
Homarr dashboard.

## Prerequisites

- A running LibrisLog instance reachable from your Homarr server
- An [embed token](/api/integrations/embed-api#creating-an-embed-token) with
  access to the embed widget endpoint
- Embed endpoints must be enabled (default: enabled). See the
  [Embed API](/api/integrations/embed-api) page for details.

## Configuration

Add an **iframe widget** to your Homarr dashboard:

1. In Homarr, navigate to your dashboard, click **Edit** → **Add a tile**.
2. Select the **Iframe** widget type.
3. Configure the widget with the following URL:

```
<LIBRISLOG-URL>/embed/v1/stats?token=<EMBED-TOKEN>
```

Replace `<LIBRISLOG-URL>` with your LibrisLog instance URL (e.g.
`https://librislog.example.com`) and `<EMBED-TOKEN>` with the token you
created.

### Customizing the Look

See the [Embed API style parameter reference](/api/integrations/embed-api#customizing-the-look)
for all available options (`theme`, `accent`, `radius`, `density`,
`hide_labels`, `show`, `lang`, `font_scale`, `layout`).

Example:

```
<LIBRISLOG-URL>/embed/v1/stats?token=<EMBED-TOKEN>&theme=dark&accent=%23f59e0b&density=compact&hide_labels=true
```

## Troubleshooting

**Widget does not appear or is cut off**

- Adjust the iframe widget size in Homarr. The widget is responsive and
  will fit the available space.
- Try `density=compact` to reduce spacing.
- Try `hide_labels=true` for a more compact display.
- Use `show` to display only the stat keys you need.

For other issues (invalid token, 403 Forbidden, empty stats, CSP errors),
see the [Embed API troubleshooting](/api/integrations/embed-api#troubleshooting)
guide.

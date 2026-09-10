# Profile

The profile page is your personal settings hub. Access it by clicking your avatar or name in the top-right corner and selecting "Profile".

![Profile page](/screenshots/profile.png)

## Profile Information

Update your first name, last name, or password. The password field is optional — leave it blank to keep your current password. A password strength indicator and complexity requirements are shown below the input.

::: tip Forgot your password?
If you have forgotten your password and mail is configured, click the **"Forgot password?"** link on the login page. Enter your email address and a reset link will be sent to you. The link is valid for one hour and can only be used once. After a successful reset, all existing sessions are invalidated and you will need to log in again.

This feature requires SMTP settings to be configured — see [Configuration](/guide/configuration#password-reset-email-optional).
:::

## Language

Switch the UI language between available locales. The change applies immediately after saving.

## Timezone

Set your preferred timezone for date/time displays (e.g., for the calendar heatmap and progress log timestamps). Your browser's detected timezone is shown as a reference.

## Theme

Choose a custom DaisyUI theme from the dropdown. The theme previews in real-time as you browse the dropdown, and the selection is saved to your profile so it persists across sessions.

## Reading Goals

Set personal reading targets that are tracked on the dashboard's **Reading Streaks & Goals** section:

| Goal | Default target |
|---|---|
| Pages per Day | 20 |
| Pages per Month | 300 |
| Books per Month | 2 |
| Books per Year | 25 |

Every goal is **disabled by default**. Toggle a goal on and set its target (at least 1) — enabled goals then appear as progress cards on the dashboard. Saving shows a confirmation notification like the other settings sections.

The **"Show reading streaks & goals on dashboard"** switch above the goals disables or re-enables the entire streaks & goals section on the dashboard.

See [Dashboard → Reading Streaks & Goals](/guide/using-librislog/dashboard#reading-streaks-goals) for details on how streaks and goal progress are calculated.

## URL/Profile Sharing

Create a read-only public view of your reading profile and share it with a URL. The shared page does not expose editing controls, notes, blurbs, or your email address.

### Create a Profile URL

1. Open **Profile** and scroll to **Share Profile**.
2. Click **Create New URL**.
3. Enter a name for the link, such as `Friends & family`.
4. Choose who can access it:
   - **Everyone** — anyone with the URL can view the profile, without logging in.
   - **Logged-in users only** — viewers must be signed in to LibrisLog.
5. Under **Content**, select the profile sections to share. Statistics can be enabled separately and configured by group.
6. Choose the language for this URL. The public page uses the link's language independently of your viewer's current UI language.
7. Under **Validity**, leave the link unlimited or set an expiration date.
8. Save the link.

The complete URL is shown once after creation. Copy it immediately or open it in a new tab. For security, the full token is not shown in the link list unless you explicitly reveal it through the link actions.

### Manage Existing URLs

Each link appears in the **Share Profile** list with its name, access level, status, token prefix, and expiry information. The available actions are:

- **Copy link** — copy the URL to the clipboard.
- **Open link** — open the read-only profile page in a new tab.
- **Edit** — change the access level, shared sections, statistics, language, or expiry date.
- **Delete** — revoke the link immediately. Anyone using it will lose access.

Treat an **Everyone** URL like a public page: anyone who receives it can view the selected information until the link expires or is deleted. Create separate links when you want different audiences or different languages.

## API Keys

Create and manage API keys for headless access to the REST API. Each key can have an optional description. Keys are shown once at creation — copy it immediately, as it cannot be retrieved later.

See the [API Keys guide](/guide/api-keys) for detailed setup instructions.

## Embed Tokens

Create scoped embed tokens for iframe dashboard integrations (e.g. Homarr). Each token can have an optional name and a comma-separated list of allowed origins. You can also configure an expiry date.

To create a token:

1. Enter a name for your token.
2. Optionally restrict allowed origins (comma-separated URLs). Leave empty for wildcard access.
3. Click **Add token**.
4. **Copy the displayed token immediately** — it is shown only once.

Existing tokens can be **rotated** (revokes the old token and creates a new one with the same settings) or **deleted** from the list.

See the [Embed API](/api/integrations/embed-api) integration guide for usage
details and a list of supported dashboard integrations.

## Data Management

Two data management tools are available:

- **Import / Export** — Export your library as JSON, CSV, or ZIP, or import from Goodreads CSV or generic CSV with field mapping and Python transforms. See [Import & Export](/guide/using-librislog/import-export).
- **Data Hygiene** — Find books with missing metadata and batch-update them. See [Data Hygiene](/guide/using-librislog/data-hygiene).

## OIDC

If the instance has OIDC authentication enabled, you can link or unlink your account to an external identity provider.

## Danger Zone

Two irreversible actions are available:

### Reset My Data

Deletes all your books, reading progress, and tags. Your account and profile settings are preserved. Type the confirmation phrase to enable the button.

### Delete Account

Permanently deletes your account and all associated data. Type the confirmation phrase to enable the button. After deletion, you are redirected to the login page.

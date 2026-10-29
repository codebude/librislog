# Administration

> [!IMPORTANT]
> The administration page is available only to users with the **admin** role. Regular users cannot access it.

![Users tab](/screenshots/admin-users.png)

## Users

### Creating a User

Admins can create new user accounts with either the `user` or `admin` role. The password must meet the complexity requirements displayed in the form.

### Editing a User

Click "Edit" next to a user to change their name, email, password, or role. You cannot change your own admin role to prevent accidental lockout.

### Deleting a User

Click "Delete" to remove a user account. You cannot delete your own account from this page — use the **Profile → Danger Zone** instead.

## External Authentication

LibrisLog can run with single sign-on (OIDC), trusted reverse-proxy authentication, or
both. The methods are independent, so a deployment can keep password login as a fallback
or turn it off entirely.

### Disabling Password Login

Set `PASSWORD_LOGIN_ENABLED=false` in the backend environment to hide the email/password
form and "Forgot password?" link. `POST /api/auth/login`, `/api/auth/forgot-password`, and
`/api/auth/reset-password` then return `403`. The first-admin setup remains available so a
new instance can be bootstrapped.

Before disabling password login, make sure every user has linked their OIDC account:
open **Profile → Single Sign-On → Link account**. Admin-created users without an OIDC
link cannot sign in while password login is disabled. If you get locked out, set
`PASSWORD_LOGIN_ENABLED=true` and restart the backend.

For account management, admins can still create users and set passwords through
**Administration → Users**. These actions do not enable password login while the flag
is off; they only store the password for later use or recovery. The profile password
field is hidden while password login is disabled.

### Trusted Reverse-Proxy Authentication

With `TRUSTED_PROXY_AUTH_ENABLED=true`, LibrisLog trusts an HTTP header set by a reverse
proxy such as Traefik BasicAuth and signs the matching user in automatically. See
[Configuration → Trusted Reverse-Proxy Authentication](/guide/configuration#trusted-reverse-proxy-authentication-optional)
for the variables and a Traefik example.

Things to keep in mind:

- The forwarded value is matched against an existing user's email address
  (case-insensitive). Set `TRUSTED_PROXY_AUTH_USER_MAP` to translate proxy usernames to
  account emails, for example `alice=alice@example.com,bob=bob@example.com`. Values not
  present in the map are used as the email directly. Only rely on that fallback when the
  proxy controls the username and users cannot set it to arbitrary email addresses;
  otherwise map every allowed username. Unknown values are ignored; accounts are never
  created automatically.
- Only requests from the configured `TRUSTED_PROXY_AUTH_IPS` are honored. Never expose the
  backend directly to clients that could spoof the header.
- When Uvicorn's proxy-header handling rewrites the connecting address from
  `X-Forwarded-For`, set `TRUSTED_PROXY_AUTH_SECRET` and have the proxy inject it, or
  restrict `FORWARDED_ALLOW_IPS` to the proxy only. Other containers on the same Docker
  network can present the header, so the secret is recommended there too.
- Because the proxy owns authentication, logging out of LibrisLog does not end the proxy
  session. The next request signs the user back in. Use the proxy's logout to switch users.
- On a shared browser, a change of proxy user replaces the LibrisLog session with the new
  user on the next request.

## Backup & Restore

![Backup and Restore tab](/screenshots/admin-backup.png)

### Creating a Backup

Downloads a ZIP archive containing the SQLite database, cover images, and import temp files. This is a complete snapshot of your library, users, and settings.

### Restoring a Backup

Upload a previously downloaded `.zip` backup file to restore the database. The app validates the backup before applying it. Backups from older versions are automatically migrated to the current schema on restore.

::: warning
Restoring overwrites all current data. Create a fresh backup first if you want to preserve your current library.
:::

### Automating Backups

The backup endpoint is accessible via the REST API, making it easy to automate with cron (or any scheduler).

First, [create an API key](/api/#creating-an-api-key) with the admin user. Then use it in a cron script:

```bash
#!/usr/bin/env bash
# Save as /etc/cron.daily/librislog-backup or add to crontab

API_KEY="lsk_your-key-here"
URL="http://localhost:8000/api/admin/backup"
DEST="/var/backups/librislog"

mkdir -p "$DEST"
curl -s -H "X-API-Key: $API_KEY" -o "$DEST/librislog-$(date +%F).zip" "$URL"

# Keep only the last 30 backups
find "$DEST" -name 'librislog-*.zip' -mtime +30 -delete
```

Crontab entry (daily at 3am):

```
0 3 * * * /path/to/backup-script.sh
```

The API returns a ZIP archive containing the SQLite database, cover images, and import temp files. No separate database dump step is needed.

## Background Maintenance

A periodic maintenance task runs automatically every hour. It performs:

- **Cover cache cleanup** — Removes orphaned cover images from disk that are no longer referenced by any book. Files modified within the last 60 minutes are preserved to avoid deleting covers that were just uploaded but not yet linked to a book entry.

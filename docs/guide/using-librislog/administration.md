# Administration

The administration page is available only to users with the **admin** role. Regular users cannot access it.

![Users tab](/screenshots/admin-users.png)

## Users

### Creating a User

Admins can create new user accounts with either the `user` or `admin` role. The password must meet the complexity requirements displayed in the form.

### Editing a User

Click "Edit" next to a user to change their name, email, password, or role. You cannot change your own admin role to prevent accidental lockout.

### Deleting a User

Click "Delete" to remove a user account. You cannot delete your own account from this page — use the **Profile → Danger Zone** instead.

## Backup & Restore

![Backup and Restore tab](/screenshots/admin-backup.png)

### Creating a Backup

Downloads the entire SQLite database as a `.db` file. This is a complete snapshot of your library, users, and settings.

### Restoring a Backup

Upload a previously downloaded `.db` file to restore the database. The app validates the backup before applying it.

::: warning
Restoring overwrites all current data. Create a fresh backup first if you want to preserve your current library.
:::

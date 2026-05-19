# Plan 50: Administration Page with Backup & Restore

## Overview

Transform the current "User Management" page into a tabbed "Administration" page with two tabs:
1. **Users** - Existing user management functionality (moved into a tab)
2. **Backup & Restore** - New functionality for full database + data directory backup/restore

This feature enables administrators to:
- Download a complete backup ZIP containing SQLite database dump + all data files (covers, import temp files)
- Restore a backup ZIP to restore the application to a previous state
- Track progress during long-running backup/restore operations
- Receive clear feedback via DaisyUI modals (no browser alerts)

---

## 1. Backend API Changes

### 1.1 New Router: `backend/app/routers/admin.py`

**Purpose**: Consolidate admin-specific endpoints (backup/restore) separate from general data import/export.

**Endpoints**:

```python
# GET /api/admin/backup
# - Admin-only endpoint
# - Generates a full backup ZIP containing:
#   - SQLite database dump (.sql file using sqlite3 CLI or .backup())
#   - Full data/ directory (covers/, import_temp/, etc.)
# - Returns: StreamingResponse with application/zip content
# - Filename: librislog-backup-{timestamp}.zip

# POST /api/admin/restore
# - Admin-only endpoint
# - Accepts multipart/form-data with backup ZIP file
# - Validates ZIP structure (must contain database.sql and data/ folder)
# - Steps:
#   1. Upload and validate ZIP
#   2. Close all DB connections
#   3. Replace SQLite database file with restored .sql
#   4. Replace data/ directory contents
#   5. Reconnect database
# - Returns: JSON with success status and summary
# - Error handling: rollback on failure, preserve original if restore fails

# GET /api/admin/backup-progress (optional SSE endpoint)
# - Server-Sent Events stream for backup progress
# - Emits events: {"stage": "database|files", "percent": 0-100, "message": "..."}
# - Use if backup takes > 5 seconds

# GET /api/admin/restore-progress (optional SSE endpoint)
# - Server-Sent Events stream for restore progress
# - Emits events: {"stage": "validation|database|files", "percent": 0-100, "message": "..."}
```

**Dependencies**:
- `require_admin` from `app.auth`
- New service: `app.services.backup_restore`

---

### 1.2 New Service: `backend/app/services/backup_restore.py`

**Purpose**: Encapsulate all backup/restore business logic.

**Functions**:

```python
def create_backup(
    session: Session,
    database_url: str,
    data_dir: str,
    covers_dir: str,
    import_temp_dir: str
) -> bytes:
    """
    Creates a backup ZIP file containing:
    - database.sql: SQLite dump using sqlite3 CLI or connection.backup()
    - data/covers/: All cover images
    - data/import_temp/: Import temp files
    - metadata.json: Backup metadata (timestamp, version, file counts)
    
    Returns ZIP file as bytes.
    """

def restore_backup(
    backup_zip_bytes: bytes,
    database_url: str,
    data_dir: str,
    covers_dir: str,
    import_temp_dir: str
) -> dict:
    """
    Restores from a backup ZIP file:
    1. Extract and validate ZIP structure
    2. Create safety backup of current state
    3. Close DB connections
    4. Restore database.sql to SQLite file
    5. Clear and restore data/ directories
    6. Reconnect database
    7. Return summary: {"restored_books": N, "restored_covers": M, ...}
    
    On error: attempt rollback to safety backup.
    """

def validate_backup_zip(zip_bytes: bytes) -> dict:
    """
    Validates backup ZIP structure without applying:
    - Contains database.sql
    - Contains data/ directory structure
    - Returns metadata from metadata.json
    """

def export_database_to_sql(database_url: str) -> str:
    """
    Creates SQL dump of SQLite database.
    Options:
    - Use sqlite3 CLI: subprocess.run(['sqlite3', db_path, '.dump'])
    - Use Python sqlite3: connection.iterdump()
    Prefer: sqlite3.iterdump() for portability (no CLI dependency)
    """

def import_database_from_sql(sql_content: str, database_url: str) -> None:
    """
    Restores SQLite database from SQL dump.
    Steps:
    1. Close all SQLAlchemy connections (engine.dispose())
    2. Delete existing .db file
    3. Create new SQLite connection
    4. Execute SQL dump
    5. Close connection
    6. Recreate SQLAlchemy engine
    """
```

**Implementation Notes**:
- Use `zipfile.ZipFile` for ZIP creation/extraction
- Use `sqlite3` module for database dump/restore (built-in Python)
- Use `pathlib.Path` for cross-platform file operations
- Include metadata.json in backup ZIP:
  ```json
  {
    "timestamp": "2026-05-19T10:00:00Z",
    "app_version": "v0.1.0-dev",
    "database_size_bytes": 1234567,
    "covers_count": 45,
    "import_temp_files_count": 2
  }
  ```
- Atomic writes: write to temp file, then rename (already established pattern in codebase)
- Error handling: preserve original database if restore fails

---

## 2. Backup ZIP Structure

```
librislog-backup-2026-05-19T10-00-00Z.zip
├── database.sql              # SQLite dump (using .iterdump())
├── metadata.json             # Backup metadata
└── data/
    ├── covers/               # All cover image files
    │   ├── local_123.jpg
    │   ├── local_456.png
    │   └── ...
    └── import_temp/          # Import temp files (if any)
        ├── user_1/
        │   └── parsed_abc123.json
        └── ...
```

**Rationale**:
- Simple, flat structure matching application layout
- database.sql is portable, human-readable text format
- data/ mirrors actual data directory structure for easy restore
- metadata.json provides validation and troubleshooting info

---

## 3. Frontend Changes

### 3.1 Rename and Restructure Admin Page

**File**: `frontend/src/routes/admin/+page.svelte`

**Changes**:

1. **Add Tabs Component**:
   - Use DaisyUI tabs (`role="tablist"`)
   - Two tabs: "Users" and "Backup & Restore"
   - Default to "Users" tab on page load
   - State management: `$state` variable to track active tab

2. **Move Existing User Management into "Users" Tab**:
   - Wrap existing user management UI (lines 142-260) in a tab panel
   - No logic changes, pure structural refactor

3. **Add New "Backup & Restore" Tab**:
   - New component or inline implementation
   - Two sections: Backup and Restore
   - See detailed design in section 3.2

**Implementation Example**:

```svelte
<script lang="ts">
  // ... existing imports and state ...
  
  let activeTab = $state<'users' | 'backup'>('users');
</script>

{#if !isAdmin}
  <div class="max-w-3xl mx-auto">
    <div class="alert alert-error"><span>Admin access required.</span></div>
  </div>
{:else}
  <div class="max-w-4xl mx-auto flex flex-col gap-6">
    <h1 class="text-2xl font-bold">{$_('admin.title')}</h1>
    
    <!-- Tabs Navigation -->
    <div role="tablist" class="tabs tabs-bordered">
      <button 
        role="tab" 
        class="tab" 
        class:tab-active={activeTab === 'users'}
        onclick={() => activeTab = 'users'}
      >
        {$_('admin.tabs.users')}
      </button>
      <button 
        role="tab" 
        class="tab" 
        class:tab-active={activeTab === 'backup'}
        onclick={() => activeTab = 'backup'}
      >
        {$_('admin.tabs.backup')}
      </button>
    </div>
    
    <!-- Tab Content -->
    {#if activeTab === 'users'}
      <!-- Existing user management UI (no changes to logic) -->
      <div class="card bg-base-100 border border-base-200 shadow-sm">
        <!-- ... existing user creation form ... -->
      </div>
      <div class="card bg-base-100 border border-base-200 shadow-sm">
        <!-- ... existing user list ... -->
      </div>
    {:else if activeTab === 'backup'}
      <!-- New Backup & Restore UI (see section 3.2) -->
      <BackupRestore />
    {/if}
  </div>
{/if}

<!-- Existing delete confirmation modal -->
<dialog class="modal" class:modal-open={pendingDeleteUserId !== null}>
  <!-- ... no changes ... -->
</dialog>
```

---

### 3.2 New Component: `frontend/src/lib/components/BackupRestore.svelte`

**Purpose**: UI for backup download and restore upload with progress tracking.

**Structure**:

```svelte
<script lang="ts">
  import { _ } from '$lib/i18n';
  import { api } from '$lib/api';
  import { toasts } from '$lib/toasts';
  
  let backupInProgress = $state(false);
  let backupProgress = $state(0);
  
  let restoreFile = $state<File | null>(null);
  let restoreInProgress = $state(false);
  let restoreProgress = $state(0);
  let showRestoreConfirmModal = $state(false);
  let restoreValidation = $state<{ valid: boolean; metadata?: any; error?: string } | null>(null);
  
  async function downloadBackup() {
    backupInProgress = true;
    backupProgress = 0;
    try {
      // Option A: Simple download (no progress)
      const blob = await api.admin.downloadBackup();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `librislog-backup-${new Date().toISOString().replace(/:/g, '-').slice(0, 19)}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toasts.add($_('admin.backup.success'), 'success');
      
      // Option B: With SSE progress (if implemented)
      // const eventSource = new EventSource('/api/admin/backup-progress');
      // eventSource.onmessage = (e) => {
      //   const data = JSON.parse(e.data);
      //   backupProgress = data.percent;
      //   if (data.percent === 100) {
      //     eventSource.close();
      //     // trigger download
      //   }
      // };
    } catch (err: unknown) {
      toasts.add(err instanceof Error ? err.message : $_('admin.backup.failed'), 'error');
    } finally {
      backupInProgress = false;
      backupProgress = 0;
    }
  }
  
  async function validateAndConfirmRestore() {
    if (!restoreFile) return;
    try {
      // Validate backup file structure
      restoreValidation = await api.admin.validateBackup(restoreFile);
      if (restoreValidation.valid) {
        showRestoreConfirmModal = true;
      } else {
        toasts.add(restoreValidation.error || $_('admin.restore.invalidBackup'), 'error');
      }
    } catch (err: unknown) {
      toasts.add(err instanceof Error ? err.message : $_('admin.restore.validationFailed'), 'error');
    }
  }
  
  async function executeRestore() {
    if (!restoreFile) return;
    showRestoreConfirmModal = false;
    restoreInProgress = true;
    restoreProgress = 0;
    try {
      const result = await api.admin.restoreBackup(restoreFile);
      toasts.add($_('admin.restore.success', { values: { books: result.restored_books } }), 'success');
      // Reload page after successful restore
      setTimeout(() => window.location.reload(), 2000);
    } catch (err: unknown) {
      toasts.add(err instanceof Error ? err.message : $_('admin.restore.failed'), 'error');
    } finally {
      restoreInProgress = false;
      restoreProgress = 0;
      restoreFile = null;
    }
  }
  
  function cancelRestore() {
    showRestoreConfirmModal = false;
    restoreValidation = null;
  }
</script>

<!-- Backup Section -->
<div class="card bg-base-100 border border-base-200 shadow-sm">
  <div class="card-body gap-4">
    <h2 class="card-title">{$_('admin.backup.title')}</h2>
    <p class="text-sm text-base-content/70">{$_('admin.backup.description')}</p>
    
    {#if backupInProgress}
      <div class="flex flex-col gap-2">
        <progress class="progress progress-primary" value={backupProgress} max="100"></progress>
        <span class="text-sm text-base-content/70">{$_('admin.backup.inProgress')}</span>
      </div>
    {:else}
      <button class="btn btn-primary btn-sm self-start" onclick={downloadBackup}>
        {$_('admin.backup.download')}
      </button>
    {/if}
  </div>
</div>

<!-- Restore Section -->
<div class="card bg-base-100 border border-base-200 shadow-sm">
  <div class="card-body gap-4">
    <h2 class="card-title">{$_('admin.restore.title')}</h2>
    <p class="text-sm text-base-content/70">{$_('admin.restore.description')}</p>
    <div class="alert alert-warning text-sm">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <span>{$_('admin.restore.warning')}</span>
    </div>
    
    {#if restoreInProgress}
      <div class="flex flex-col gap-2">
        <progress class="progress progress-primary" value={restoreProgress} max="100"></progress>
        <span class="text-sm text-base-content/70">{$_('admin.restore.inProgress')}</span>
      </div>
    {:else}
      <input 
        type="file" 
        class="file-input file-input-bordered file-input-sm" 
        accept=".zip"
        onchange={(e) => restoreFile = e.currentTarget.files?.[0] || null}
      />
      {#if restoreFile}
        <button class="btn btn-warning btn-sm self-start" onclick={validateAndConfirmRestore}>
          {$_('admin.restore.upload')}
        </button>
      {/if}
    {/if}
  </div>
</div>

<!-- Restore Confirmation Modal (DaisyUI) -->
<dialog class="modal" class:modal-open={showRestoreConfirmModal}>
  <div class="modal-box">
    <h3 class="text-lg font-bold">{$_('admin.restore.confirmTitle')}</h3>
    <p class="py-3 text-sm text-base-content/70">{$_('admin.restore.confirmBody')}</p>
    
    {#if restoreValidation?.metadata}
      <div class="bg-base-200 rounded p-3 text-xs font-mono mb-3">
        <div>{$_('admin.restore.backupDate')}: {restoreValidation.metadata.timestamp}</div>
        <div>{$_('admin.restore.backupVersion')}: {restoreValidation.metadata.app_version}</div>
        <div>{$_('admin.restore.coversCount')}: {restoreValidation.metadata.covers_count}</div>
      </div>
    {/if}
    
    <div class="alert alert-error text-sm mb-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span>{$_('admin.restore.confirmWarning')}</span>
    </div>
    
    <div class="modal-action">
      <button type="button" class="btn btn-ghost" onclick={cancelRestore}>{$_('common.cancel')}</button>
      <button type="button" class="btn btn-warning" onclick={executeRestore}>{$_('admin.restore.confirm')}</button>
    </div>
  </div>
  <form method="dialog" class="modal-backdrop">
    <button type="button" onclick={cancelRestore}>{$_('common.close')}</button>
  </form>
</dialog>
```

**Design Notes**:
- **Backup**: Single button that triggers download, simple progress indicator
- **Restore**: File picker → validation → DaisyUI modal confirmation → execution
- **Progress**: Use `<progress>` element (DaisyUI styled) for visual feedback
- **Warnings**: Alert boxes to emphasize data loss risk during restore
- **Modal**: DaisyUI modal (not browser `confirm()`) for restore confirmation
- **Metadata Display**: Show backup timestamp, version, file counts before restore
- **Error Handling**: Toast notifications for all error states

---

### 3.3 API Client Updates

**File**: `frontend/src/lib/api.ts`

**Add new namespace**:

```typescript
export const api = {
  // ... existing namespaces ...
  
  admin: {
    async downloadBackup(): Promise<Blob> {
      const response = await fetch('/api/admin/backup', {
        method: 'GET',
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Backup failed: ${response.statusText}`);
      }
      return response.blob();
    },
    
    async validateBackup(file: File): Promise<{ valid: boolean; metadata?: any; error?: string }> {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('/api/admin/validate-backup', {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Validation failed: ${response.statusText}`);
      }
      return response.json();
    },
    
    async restoreBackup(file: File): Promise<{ restored_books: number; restored_covers: number }> {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('/api/admin/restore', {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Restore failed');
      }
      return response.json();
    },
  },
};
```

---

## 4. Security Considerations

### 4.1 Authorization

- **All backup/restore endpoints require admin role**: Use `require_admin` dependency
- **Existing pattern**: Already established in `users.py` router
- **No additional auth logic needed**: Leverage existing `app.auth.require_admin`

### 4.2 File Validation

- **Backup ZIP validation**:
  - Check ZIP file structure before restore
  - Validate presence of `database.sql` and `data/` directory
  - Check file sizes to prevent ZIP bombs (limit to reasonable size, e.g., 500MB)
  - Verify metadata.json schema

- **SQL injection prevention**:
  - No user input in SQL dump/restore (automated process)
  - Use parameterized queries if any filtering is needed

### 4.3 Data Integrity

- **Safety backup before restore**:
  - Create temporary backup of current database + data/ before restore
  - On restore failure, rollback to safety backup
  - Clean up safety backup after successful restore

- **Atomic operations**:
  - Use temp files + rename pattern (already in codebase)
  - Close all DB connections before database file replacement
  - Recreate engine after restore

### 4.4 Rate Limiting (Future Enhancement)

- Consider adding rate limiting to backup/restore endpoints to prevent abuse
- Not critical for MVP (admin-only, low traffic)

---

## 5. i18n Translation Keys

### 5.1 English (`frontend/src/lib/i18n/locales/en.json`)

Add to `"admin"` section:

```json
{
  "admin": {
    "title": "Administration",
    "tabs": {
      "users": "Users",
      "backup": "Backup & Restore"
    },
    "backup": {
      "title": "Backup",
      "description": "Download a complete backup of your library including all books, covers, and data.",
      "download": "Download Backup",
      "success": "Backup downloaded successfully",
      "failed": "Backup download failed",
      "inProgress": "Creating backup..."
    },
    "restore": {
      "title": "Restore",
      "description": "Restore your library from a previous backup file.",
      "warning": "⚠️ Warning: Restoring will replace ALL current data. Make sure you have a recent backup before proceeding.",
      "upload": "Upload and Restore",
      "success": "Restore completed successfully. Restored {books} books.",
      "failed": "Restore failed",
      "inProgress": "Restoring backup...",
      "validationFailed": "Could not validate backup file",
      "invalidBackup": "Invalid backup file structure",
      "confirmTitle": "Confirm Restore",
      "confirmBody": "Are you sure you want to restore from this backup? This will replace all current data and cannot be undone.",
      "confirmWarning": "⚠️ This action is irreversible. All current data will be lost.",
      "confirm": "Restore Now",
      "backupDate": "Backup Date",
      "backupVersion": "App Version",
      "coversCount": "Covers"
    }
  }
}
```

**Update existing key**:
- Change `"admin.title"` from `"User Management"` to `"Administration"`

### 5.2 German (`frontend/src/lib/i18n/locales/de.json`)

Add to `"admin"` section:

```json
{
  "admin": {
    "title": "Administration",
    "tabs": {
      "users": "Benutzer",
      "backup": "Sicherung & Wiederherstellung"
    },
    "backup": {
      "title": "Sicherung",
      "description": "Lade eine vollständige Sicherung deiner Bibliothek herunter, einschließlich aller Bücher, Cover und Daten.",
      "download": "Sicherung herunterladen",
      "success": "Sicherung erfolgreich heruntergeladen",
      "failed": "Sicherung fehlgeschlagen",
      "inProgress": "Erstelle Sicherung..."
    },
    "restore": {
      "title": "Wiederherstellung",
      "description": "Stelle deine Bibliothek aus einer früheren Sicherungsdatei wieder her.",
      "warning": "⚠️ Warnung: Die Wiederherstellung ersetzt ALLE aktuellen Daten. Stelle sicher, dass du eine aktuelle Sicherung hast, bevor du fortfährst.",
      "upload": "Hochladen und Wiederherstellen",
      "success": "Wiederherstellung erfolgreich abgeschlossen. {books} Bücher wiederhergestellt.",
      "failed": "Wiederherstellung fehlgeschlagen",
      "inProgress": "Stelle Sicherung wieder her...",
      "validationFailed": "Sicherungsdatei konnte nicht validiert werden",
      "invalidBackup": "Ungültige Sicherungsdateistruktur",
      "confirmTitle": "Wiederherstellung bestätigen",
      "confirmBody": "Möchtest du wirklich aus dieser Sicherung wiederherstellen? Dies ersetzt alle aktuellen Daten und kann nicht rückgängig gemacht werden.",
      "confirmWarning": "⚠️ Diese Aktion ist unwiderruflich. Alle aktuellen Daten gehen verloren.",
      "confirm": "Jetzt wiederherstellen",
      "backupDate": "Sicherungsdatum",
      "backupVersion": "App-Version",
      "coversCount": "Cover"
    }
  }
}
```

**Update existing key**:
- Change `"admin.title"` from `"Benutzerverwaltung"` to `"Administration"`

---

## 6. Configuration Changes

### 6.1 Add Settings for Backup/Restore

**File**: `backend/app/config.py`

**New settings** (optional, use existing if sufficient):

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Backup/Restore settings
    backup_max_size_mb: int = 500  # Maximum backup file size for restore
    backup_temp_dir: str = "./data/backup_temp"  # Temp directory for backup operations
```

**Rationale**: These are optional. Existing settings (`database_url`, `covers_dir`, `import_temp_dir`) are sufficient for core functionality. Add only if configurable limits are needed.

---

## 7. Database Considerations

### 7.1 No Schema Changes

- **No new tables/models required**: Backup/restore operates on existing database
- **No migrations needed**: This is a pure operational feature

### 7.2 Connection Management

- **Critical**: Close all database connections before restoring
  ```python
  from app.database import engine
  engine.dispose()  # Close all pooled connections
  ```
- **After restore**: Recreate engine to establish fresh connections
  ```python
  from app.database import get_engine
  engine = get_engine()  # Reconnect
  ```

### 7.3 SQLite Backup Methods

**Option A: `.dump` via `sqlite3` CLI**:
```bash
sqlite3 ./data/librislog.db .dump > database.sql
```
- Pros: Standard, well-tested
- Cons: Requires sqlite3 CLI installed

**Option B: Python `sqlite3.iterdump()`**:
```python
import sqlite3
conn = sqlite3.connect('./data/librislog.db')
with open('database.sql', 'w') as f:
    for line in conn.iterdump():
        f.write(f'{line}\n')
conn.close()
```
- Pros: Pure Python, no external dependencies
- Cons: Slightly slower for large databases

**Recommendation**: Use Option B (Python `iterdump`) for portability and consistency with codebase philosophy.

---

## 8. Testing Strategy

### 8.1 Manual Testing Checklist

**Backup**:
- [ ] Click "Download Backup" button
- [ ] Verify ZIP file downloads with correct timestamp filename
- [ ] Extract ZIP and verify structure (database.sql, data/, metadata.json)
- [ ] Verify database.sql contains valid SQL
- [ ] Verify covers are present in data/covers/
- [ ] Verify metadata.json contains correct counts

**Restore**:
- [ ] Select valid backup ZIP file
- [ ] Verify validation shows metadata before restore
- [ ] Cancel restore, verify no changes made
- [ ] Confirm restore, verify all data is restored
- [ ] Verify books, covers, tags, progress are restored correctly
- [ ] Verify application works normally after restore
- [ ] Test restore with invalid ZIP, verify error handling
- [ ] Test restore with corrupted database.sql, verify rollback

**UI/UX**:
- [ ] Verify "Administration" title (not "User Management")
- [ ] Verify tabs switch correctly between Users and Backup
- [ ] Verify progress indicators during backup/restore
- [ ] Verify DaisyUI modal shows for restore confirmation
- [ ] Verify warning messages are visible and clear
- [ ] Verify translations work in English and German

**Security**:
- [ ] Verify non-admin users cannot access backup/restore
- [ ] Verify API endpoints return 403 for non-admin users
- [ ] Verify large ZIP files are rejected (if size limit implemented)

### 8.2 Edge Cases

- **Empty database**: Backup should work, restore to empty state
- **Large database**: Test with 1000+ books, verify performance
- **Missing covers**: Backup should succeed even if some covers are missing
- **Concurrent access**: Test restore while another user is logged in (not supported, but should fail gracefully)
- **Disk space**: Test restore with insufficient disk space (should fail gracefully)

---

## 9. Implementation Order

### Phase 1: Backend Foundation (Priority: High)

**Step 1.1**: Create `backend/app/services/backup_restore.py`
- Implement `export_database_to_sql()` function
- Test: Create SQL dump of development database, verify valid SQL
- Implement `create_backup()` function
- Test: Generate backup ZIP, verify structure
- Estimated time: 2-3 hours

**Step 1.2**: Create `backend/app/routers/admin.py`
- Implement `GET /api/admin/backup` endpoint
- Test: Call endpoint via curl, verify ZIP download
- Estimated time: 1 hour

**Step 1.3**: Implement restore logic in `backup_restore.py`
- Implement `validate_backup_zip()` function
- Implement `import_database_from_sql()` function
- Implement `restore_backup()` function
- Test: Restore from backup, verify data integrity
- Estimated time: 3-4 hours

**Step 1.4**: Complete `admin.py` router
- Implement `POST /api/admin/validate-backup` endpoint
- Implement `POST /api/admin/restore` endpoint
- Test: End-to-end backup → restore cycle
- Estimated time: 2 hours

---

### Phase 2: Frontend UI (Priority: High)

**Step 2.1**: Restructure admin page with tabs
- Modify `frontend/src/routes/admin/+page.svelte`
- Add tab state management
- Wrap existing user management in "Users" tab
- Test: Verify existing user management still works
- Estimated time: 1 hour

**Step 2.2**: Create `BackupRestore.svelte` component
- Implement backup section with download button
- Implement restore section with file picker
- Test: Verify UI renders correctly (no API calls yet)
- Estimated time: 2 hours

**Step 2.3**: Integrate API calls
- Add `admin` namespace to `frontend/src/lib/api.ts`
- Connect backup download button to API
- Connect restore upload to API with validation
- Test: End-to-end backup/restore via UI
- Estimated time: 2 hours

**Step 2.4**: Add progress indicators and modals
- Implement DaisyUI confirmation modal for restore
- Add progress bars during backup/restore
- Add metadata display in confirmation modal
- Test: Verify modal UX and progress feedback
- Estimated time: 1-2 hours

---

### Phase 3: i18n and Polish (Priority: Medium)

**Step 3.1**: Add translation keys
- Update `frontend/src/lib/i18n/locales/en.json`
- Update `frontend/src/lib/i18n/locales/de.json`
- Update page title from "User Management" to "Administration"
- Test: Verify all UI text is translated
- Estimated time: 30 minutes

**Step 3.2**: Error handling and edge cases
- Add comprehensive error messages
- Test with invalid ZIP files
- Test with corrupted databases
- Add file size validation
- Estimated time: 1-2 hours

---

### Phase 4: Documentation and Testing (Priority: Medium)

**Step 4.1**: Update README or docs
- Document backup/restore feature
- Add screenshots of new admin tabs
- Document backup ZIP structure
- Add troubleshooting tips
- Estimated time: 1 hour

**Step 4.2**: Manual testing cycle
- Run through entire testing checklist (section 8.1)
- Test both English and German locales
- Test as admin and non-admin users
- Document any bugs found
- Estimated time: 2 hours

---

### Phase 5: Optional Enhancements (Priority: Low)

**Step 5.1**: Add SSE progress for long operations
- Implement `GET /api/admin/backup-progress` SSE endpoint
- Implement `GET /api/admin/restore-progress` SSE endpoint
- Connect frontend to SSE streams
- Test with large databases (1000+ books)
- Estimated time: 3-4 hours

**Step 5.2**: Scheduled backups (future)
- Add cron/scheduler for automatic backups
- Add backup retention policy
- Add email notifications for backup status
- Estimated time: TBD (future feature)

---

## 10. Risks and Mitigations

### Risk 1: Data Loss During Restore

**Impact**: High  
**Likelihood**: Medium  
**Mitigation**:
- Create safety backup before restore
- Implement rollback mechanism on failure
- Add prominent warnings in UI
- Require explicit confirmation with metadata display

### Risk 2: Database Connection Issues

**Impact**: High  
**Likelihood**: Low  
**Mitigation**:
- Properly dispose all connections before restore
- Use try/finally blocks to ensure cleanup
- Test connection handling thoroughly
- Add detailed error logging

### Risk 3: Large File Performance

**Impact**: Medium  
**Likelihood**: Low  
**Mitigation**:
- Test with large databases (1000+ books, 500+ MB)
- Add file size limits for restore
- Implement streaming for backup generation if needed
- Add timeout handling for long operations

### Risk 4: Concurrent Access During Restore

**Impact**: High  
**Likelihood**: Low  
**Mitigation**:
- Document that restore should be done during maintenance window
- Consider adding "maintenance mode" flag (future enhancement)
- Add warning in UI about concurrent users
- Test restore failure scenarios

### Risk 5: Incomplete Backup

**Impact**: Medium  
**Likelihood**: Low  
**Mitigation**:
- Include metadata.json with file counts for verification
- Validate ZIP structure before restore
- Add checksums to metadata (future enhancement)
- Test with missing files scenarios

---

## 11. Success Criteria

**MVP Complete When**:
- [x] Admin page renamed to "Administration" with tabbed layout
- [x] User management moved to "Users" tab (no functionality changes)
- [x] "Backup & Restore" tab added with functional UI
- [x] Backup downloads complete ZIP with database + data files
- [x] Restore validates and restores from backup ZIP
- [x] DaisyUI modal used for restore confirmation (no browser alerts)
- [x] Progress indicators shown during backup/restore
- [x] All UI text translated (English + German)
- [x] Security: Only admin users can access backup/restore
- [x] Error handling: Clear error messages for all failure modes
- [x] Testing: Manual testing checklist passed

**Quality Indicators**:
- Zero data loss in restore testing
- All existing functionality still works after UI refactor
- No accessibility regressions (keyboard navigation, screen readers)
- Consistent with existing codebase patterns (API structure, component style)

---

## 12. Open Questions and Decisions

### Q1: Include import_temp in backup?

**Decision**: Yes, include `import_temp/` directory  
**Rationale**: Complete state restoration, minimal storage cost  
**Alternative**: Exclude import_temp (user can re-import if needed)

### Q2: Backup scheduling?

**Decision**: Not in MVP, manual only  
**Rationale**: Admin-driven feature, avoid complexity  
**Future**: Add scheduled backups with retention policy

### Q3: Restore progress tracking method?

**Decision**: Start with simple boolean flag (inProgress), add SSE if needed  
**Rationale**: SSE adds complexity, test performance first  
**Trigger**: If restore takes >10 seconds on typical data, add SSE

### Q4: Multiple backup versions management?

**Decision**: Not in MVP, user manages backup files manually  
**Rationale**: Avoid building backup storage management  
**Future**: Add backup history list in UI

### Q5: Backup encryption?

**Decision**: Not in MVP  
**Rationale**: User can encrypt ZIP files externally if needed  
**Future**: Add optional encryption with passphrase

---

## 13. File Checklist

### Files to Create:
- [ ] `backend/app/routers/admin.py` - Admin endpoints
- [ ] `backend/app/services/backup_restore.py` - Backup/restore logic
- [ ] `frontend/src/lib/components/BackupRestore.svelte` - Backup/restore UI component

### Files to Modify:
- [ ] `frontend/src/routes/admin/+page.svelte` - Add tabs, rename page
- [ ] `frontend/src/lib/api.ts` - Add admin API namespace
- [ ] `frontend/src/lib/i18n/locales/en.json` - Add translation keys
- [ ] `frontend/src/lib/i18n/locales/de.json` - Add translation keys
- [ ] `backend/app/config.py` - Add backup settings (optional)
- [ ] `backend/app/routers/__init__.py` - Register admin router
- [ ] `backend/app/main.py` - Mount admin router (if needed)

### Files to Review (No Changes Expected):
- [ ] `backend/app/auth.py` - Verify require_admin works as expected
- [ ] `backend/app/models.py` - Verify no schema changes needed
- [ ] `backend/app/database.py` - Verify engine disposal works correctly

---

## 14. Appendix: Code Patterns to Follow

### A. Backend Service Pattern (from `data_export.py`):
```python
# Use SQLModel session
from sqlmodel import Session

# Return bytes for files
def create_backup(...) -> bytes:
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, 'w', ZIP_DEFLATED) as zip_file:
        # Add files
    return zip_buffer.getvalue()

# Use pathlib for paths
from pathlib import Path
covers_path = Path(covers_dir)
```

### B. Backend Router Pattern (from `data.py`):
```python
from fastapi import APIRouter, Depends, HTTPException, Response
from app.auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/backup")
def download_backup(
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    # ... logic ...
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

### C. Frontend Component Pattern (from `DataExport.svelte`):
```typescript
// Use $state for reactive state
let exporting = $state(false);

// Use $_ for translations
import { _ } from '$lib/i18n';
<h2>{$_('admin.backup.title')}</h2>

// Use toasts for notifications
import { toasts } from '$lib/toasts';
toasts.add($_('admin.backup.success'), 'success');

// Use blob download pattern
const blob = await api.admin.downloadBackup();
const url = URL.createObjectURL(blob);
const link = document.createElement('a');
link.href = url;
link.download = filename;
document.body.appendChild(link);
link.click();
link.remove();
URL.revokeObjectURL(url);
```

### D. Modal Pattern (from `admin/+page.svelte`):
```svelte
<dialog class="modal" class:modal-open={showModal}>
  <div class="modal-box">
    <h3 class="text-lg font-bold">{$_('modal.title')}</h3>
    <p class="py-3">{$_('modal.body')}</p>
    <div class="modal-action">
      <button class="btn btn-ghost" onclick={cancel}>{$_('common.cancel')}</button>
      <button class="btn btn-primary" onclick={confirm}>{$_('common.confirm')}</button>
    </div>
  </div>
  <form method="dialog" class="modal-backdrop">
    <button onclick={cancel}>{$_('common.close')}</button>
  </form>
</dialog>
```

---

## End of Plan

**Estimated Total Implementation Time**: 20-25 hours  
**Priority**: High (core admin feature)  
**Dependencies**: None (uses existing auth, database, data patterns)  
**Next Steps**: Review plan → Begin Phase 1 (Backend Foundation)

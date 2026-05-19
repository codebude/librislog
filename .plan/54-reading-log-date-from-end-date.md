# Plan: Use Book's `end_date` for Reading Log Entry Timestamps During Mass Import

**Status:** Ready for Implementation  
**Priority:** Medium  
**Complexity:** Low

---

## 1. Overview

### Current Behavior
When a mass import runs with `create_progress_for_read=true`, the system creates reading log entries (`ReadingProgress`) for books with status `read` and a non-null `page_count`. These entries use the **current timestamp** (`utcnow()`) as their `created_at` value, regardless of when the book was actually finished.

### Desired Behavior
- If a book has a `date_finished` (the "end date"), use **that date** as the `created_at` timestamp for the reading log entry.
- Only fall back to the current date when `date_finished` is `None`.

### Rationale
Users importing historical reading data expect reading log timestamps to reflect the **actual completion date**, not the import date. This ensures statistics and timelines remain accurate after migration.

---

## 2. Files to Modify

### 2.1 `backend/app/services/data_import.py` — Adjust `created_at` logic

**Location:** Lines 507–513 in `execute_import()` function  
**Current Code:**
```python
if create_progress_for_read and reading_status == ReadingStatus.read and page_count is not None:
    progress_entry = ReadingProgress(
        book_id=book.id,
        user_id=user.id,
        page=page_count,
    )
    session.add(progress_entry)
```

**Proposed Change:**
```python
if create_progress_for_read and reading_status == ReadingStatus.read and page_count is not None:
    # Use the book's end date if available; otherwise fall back to current time
    log_date = date_finished if date_finished is not None else utcnow()
    
    progress_entry = ReadingProgress(
        book_id=book.id,
        user_id=user.id,
        page=page_count,
        created_at=log_date,
    )
    session.add(progress_entry)
```

**Reasoning:**
- `date_finished` is already parsed and validated earlier in the function (line 472).
- `utcnow()` is already imported at the top of the file (line 15).
- The `ReadingProgress` model accepts `created_at` as an optional parameter (defaults via `Field(default_factory=utcnow)` in `models.py` line 141).
- Explicitly setting `created_at` overrides the default factory, allowing us to use historical dates.

---

## 3. Edge Cases and Validation

### 3.1 Missing `date_finished`
**Scenario:** Book is marked as `read` but has no `date_finished`.  
**Behavior:** Fall back to `utcnow()` — same as current behavior.  
**Handling:** Already covered by the proposed conditional logic.

### 3.2 Invalid `date_finished`
**Scenario:** Malformed date string fails parsing.  
**Behavior:** Validation already catches this in line 472 via `_parse_datetime()`. The row import fails before reaching progress creation.  
**Handling:** No additional validation needed.

### 3.3 `date_finished` in the future
**Scenario:** Imported date is after the current date.  
**Behavior:** System allows it; SQLite/PostgreSQL accept future timestamps.  
**Risk:** Low — data import is user-controlled, and statistics endpoints typically filter by date range.  
**Recommendation:** Accept as-is. If needed, add a warning in validation (separate ticket).

### 3.4 Timezone behavior
**Scenario:** `date_finished` has a timezone; `created_at` is stored as UTC.  
**Behavior:**  
- `_parse_datetime()` already normalizes all dates to UTC (line 286: `dt.replace(tzinfo=timezone.utc)`).  
- `UtcDateTime` type in `models.py` strips timezone info during storage (line 18).  
**Handling:** Already consistent; no additional work required.

### 3.5 `create_progress_for_read=false`
**Scenario:** User disables automatic reading log creation.  
**Behavior:** No `ReadingProgress` entries are created.  
**Handling:** No change; existing guard clause prevents execution.

---

## 4. Data Flow Summary

```
CSV/JSON upload
  ↓
parse_upload() → file_id + rows
  ↓
execute_import(file_id, ..., create_progress_for_read=True)
  ↓
  For each row:
    - Parse row data (title, status, dates, ...)
    - Validate date_finished via _parse_datetime() → UTC datetime or None
    - Create Book record
    - IF (create_progress_for_read AND status==read AND page_count exists):
        → Create ReadingProgress with created_at = date_finished ?? utcnow()
```

---

## 5. Tests to Update/Add

### 5.1 Update Existing Test: `test_import.py`
**File:** `backend/tests/test_import.py`

#### 5.1.1 Add new test case
```python
def test_import_with_progress_uses_end_date_when_present(client: TestClient):
    """When create_progress_for_read is enabled and date_finished is set, reading log uses that date."""
    # Implementation: See section 6.1 below
```

#### 5.1.2 Add test for fallback behavior
```python
def test_import_with_progress_falls_back_to_current_date(client: TestClient):
    """When create_progress_for_read is enabled but date_finished is missing, use current timestamp."""
    # Implementation: See section 6.1 below
```

### 5.2 Integration Test
**Scenario:** Import a CSV with multiple books:
- Book A: `read` status, `date_finished=2024-01-15`, `page_count=300` → log date = 2024-01-15
- Book B: `read` status, no `date_finished`, `page_count=200` → log date = current time
- Book C: `read` status, `date_finished=2025-06-01T12:00:00Z`, `page_count=150` → log date = 2025-06-01 (UTC)

**Assertions:**
- `ReadingProgress.created_at` for Book A matches 2024-01-15 (UTC).
- `ReadingProgress.created_at` for Book B is within 1 second of test execution time.
- `ReadingProgress.created_at` for Book C matches 2025-06-01T12:00:00Z.

---

## 6. Implementation Steps

### Step 1: Modify `data_import.py`
1. Locate the `execute_import()` function, specifically lines 507–513.
2. Replace the `ReadingProgress` instantiation block with the proposed code from section 2.1.
3. Add inline comment explaining the fallback logic.

### Step 2: Write tests
1. Open `backend/tests/test_import.py`.
2. Add the two new test functions described in section 5.1.
3. Use monkeypatching to control `utcnow()` for deterministic fallback testing.

**Example test skeleton:**
```python
def test_import_with_progress_uses_end_date_when_present(client: TestClient):
    payload = {
        "candidate": {
            "title": "Historical Book",
            "page_count": 300,
            "date_finished": "2024-01-15T00:00:00Z",
            "source": "test",
        },
        "reading_status": "read",
        "create_progress_for_read": True,
    }
    # POST to import endpoint
    # Query ReadingProgress for the created book
    # Assert created_at == datetime(2024, 1, 15, tzinfo=UTC)
```

### Step 3: Manual verification
1. Import a CSV with historical `date_finished` values.
2. Navigate to **Timeline** page in the frontend.
3. Confirm reading log entries appear on the correct dates (not all on import day).
4. Check **Statistics** page — verify "Pages Read Over Time" chart reflects historical data.

### Step 4: Update documentation (if applicable)
- **User-facing:** Mention in data import help text that reading logs use the book's finish date.
- **Developer-facing:** Update any internal notes about import behavior.

---

## 7. Rollout and Verification

### Pre-deployment Checklist
- [ ] Code review approved.
- [ ] All new tests pass (`pytest backend/tests/test_import.py -k progress`).
- [ ] Existing import tests still pass (no regressions).
- [ ] Manual test with sample CSV confirms correct date assignment.

### Deployment
- No database migration required (existing schema supports custom `created_at` values).
- No frontend changes required (feature is backend-only).
- No environment variable changes.

### Post-deployment Verification
1. **Smoke Test:** Import a small CSV with mixed `date_finished` values.
2. **Data Integrity:** Query a sample of imported reading logs:
   ```sql
   SELECT book_id, created_at, page FROM reading_progress WHERE user_id = <test_user_id> ORDER BY created_at;
   ```
3. **Frontend Check:** Verify timeline and statistics pages display correct data.

### Rollback Plan
If issues arise, revert the change in `data_import.py` to restore default `utcnow()` behavior. No data corruption risk — only affects newly imported records.

---

## 8. Open Questions

**Q1:** Should we add a UI indicator showing whether a reading log was manually created vs. auto-generated during import?  
**A:** Out of scope. Current plan treats all reading logs equally.

**Q2:** Should future dates in `date_finished` be rejected during validation?  
**A:** Defer to a future enhancement. Current implementation allows it; statistics filtering will handle edge cases.

**Q3:** Does this affect the `/api/books/{book_id}/progress` POST endpoint?  
**A:** No. That endpoint always uses `utcnow()` for user-generated reading logs. This change only affects mass import.

---

## 9. Related Work

- **Prerequisite:** None (self-contained change).
- **Follow-up Ideas:**
  - Add validation warning for future dates in import preview.
  - Allow users to edit `created_at` timestamps on reading logs (separate feature).
  - Support importing reading logs as a separate CSV (advanced bulk import).

---

## 10. Estimated Effort

- **Code Change:** 5 minutes (single function, 3 lines modified)
- **Tests:** 30 minutes (2 new test cases + manual verification)
- **Review + QA:** 20 minutes
- **Total:** ~1 hour

---

## 11. Checklist for Implementation

- [ ] Read this plan in full.
- [ ] Modify `backend/app/services/data_import.py` (lines 507–513).
- [ ] Add test case for historical date behavior.
- [ ] Add test case for fallback to current date.
- [ ] Run all tests: `pytest backend/tests/test_import.py`.
- [ ] Manual import test with sample CSV.
- [ ] Verify timeline page displays correct dates.
- [ ] Verify statistics page reflects historical data.
- [ ] Code review.
- [ ] Merge and deploy.

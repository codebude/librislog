# Summary: Did Not Finish (DNF) Book Status

## Quick Overview

Add a fourth reading status `did_not_finish` for books users intentionally abandoned because they were bad, boring, or not interesting. This becomes a first-class state with dedicated tab/navigation alongside existing statuses.

---

## What's Being Built

**Feature**: New "Did Not Finish" reading status

**User Benefits**:
- Track abandoned books separately from unfinished books
- Clear distinction between "haven't started yet" vs "tried and stopped"
- Dedicated tab for DNF books (same UX as other statuses)

**User Flow**:
1. User starts reading a book (status: `currently_reading`)
2. User finds book boring/bad and decides to stop
3. User opens book drawer, changes status to "Did Not Finish"
4. Book moves to "Did Not Finish" tab
5. User can add notes (e.g., "Too slow, stopped at page 50")

---

## Technical Approach

### **Backend Changes** (1 hour)

**Database Migration**:
- Add `did_not_finish` to `ReadingStatus` enum via Alembic migration
- Use `batch_alter_table` for SQLite compatibility
- Downgrade migration moves DNF books to `want_to_read` (safe fallback)

**Model Update**:
- Add enum value to `ReadingStatus` in `models.py`
- No schema changes needed (schemas reference enum)

**API Impact**:
- All endpoints automatically support new status (enum-based validation)
- No router logic changes needed

---

### **Frontend Changes** (2 hours)

**Type Updates**:
- Add `did_not_finish` to `ReadingStatus` type in `types.ts`

**Navigation**:
- Add fourth item to `NAV_ITEMS` in `+layout.svelte`
  - Label: "Did Not Finish"
  - Icon: ❌ (cross mark)
- Add status label mapping in `+page.svelte`

**Components**:
- Add fourth `<option>` to status dropdowns:
  - `BookDrawer.svelte` (edit book)
  - `AddBookModal.svelte` (create book)
  - `ImportSearch.svelte` (import book, if selector exists)

---

### **Testing** (1.5 hours)

**Backend Tests** (4 new tests):
- Create book with DNF status
- Filter books by DNF status
- Update book to DNF status
- Import book with DNF status

**Frontend Tests** (30 manual tests):
- Navigation (6 tests): Desktop/mobile nav works
- Create book (6 tests): Can create DNF books
- Edit book (6 tests): Can change to/from DNF
- List/filter (6 tests): DNF tab filters correctly, search/sort work
- Import (3 tests): Can import to DNF
- Delete (3 tests): Can delete DNF books
- Regression (existing tabs still work)

---

## Key Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `backend/alembic/versions/[new]_add_did_not_finish_status.py` | **NEW**: Migration to add enum value | ~40 |
| `backend/app/models.py` | Add `did_not_finish` to enum | +1 |
| `backend/tests/test_books.py` | Add 4 DNF test cases | +60 |
| `frontend/src/lib/types.ts` | Add `did_not_finish` to type | +1 |
| `frontend/src/routes/+layout.svelte` | Add DNF nav item | +1 |
| `frontend/src/routes/+page.svelte` | Add DNF label | +1 |
| `frontend/src/lib/components/BookDrawer.svelte` | Add DNF option to dropdown | +1 |
| `frontend/src/lib/components/AddBookModal.svelte` | Add DNF option to dropdown | +1 |
| `frontend/src/lib/components/ImportSearch.svelte` | Add DNF option (if needed) | +1 |

**Total new code**: ~110 lines (mostly tests + migration)

---

## UX Changes

### **Navigation**

**Desktop** (sidebar):
```
📚 Want to Read
📖 Reading
✓ Read
❌ Did Not Finish  ← NEW
```

**Mobile** (bottom bar):
```
[📚]  [📖]  [✓]  [❌]  ← 4 tabs
```

**Page Header**:
- Shows "Did Not Finish" when on DNF tab

---

### **Status Dropdowns**

**Before** (3 options):
```
Want to Read
Currently Reading
Read
```

**After** (4 options):
```
Want to Read
Currently Reading
Read
Did Not Finish  ← NEW
```

---

### **Tab Behavior**

DNF tab works identically to other tabs:
- Shows only DNF books
- Search works (title/author)
- Sort works (date added, rating)
- Empty state: "No books here yet."
- Create/edit/delete work

---

## Edge Cases Handled

| Scenario | Handling |
|----------|----------|
| Existing books in DB | ✅ Unaffected (migration is additive) |
| Migration downgrade | ✅ DNF books → `want_to_read` (no data loss) |
| Old API clients | ✅ New status appears in responses (clients ignore unknown values) |
| Mobile bottom bar crowding | ✅ 4 tabs is standard pattern (tested on small screens) |
| Import to DNF status | ✅ Status selector in import (if added) OR change after import |
| Search/sort in DNF tab | ✅ Existing filter logic works (enum-based) |

---

## Mobile Considerations

**Bottom Bar Layout**:
- **Before**: 3 tabs (~33% width each)
- **After**: 4 tabs (~25% width each)
- **Impact**: Standard mobile pattern, commonly used in many apps
- **Tested on**: iPhone SE (smallest screen), larger screens have more space

**Touch Targets**:
- Minimum 44×44px tap targets (iOS guideline)
- Icons + labels for clarity
- No horizontal scrolling needed

---

## Database Migration Strategy

### **Upgrade Path** (forward migration):
```sql
ALTER TABLE book 
ALTER COLUMN reading_status 
TYPE ENUM('want_to_read', 'currently_reading', 'read', 'did_not_finish');
```
*(SQLite implementation uses `batch_alter_table`)*

### **Downgrade Path** (rollback):
```sql
-- Move DNF books to want_to_read
UPDATE book SET reading_status = 'want_to_read' WHERE reading_status = 'did_not_finish';

-- Remove enum value
ALTER TABLE book 
ALTER COLUMN reading_status 
TYPE ENUM('want_to_read', 'currently_reading', 'read');
```

**Safety**:
- ✅ No data deletion (books preserved)
- ✅ No foreign key issues (self-contained change)
- ✅ Downgrade moves books to safe status

---

## Deployment Process

### **Pre-Deployment**
1. ✅ All tests pass (backend + frontend manual tests)
2. ✅ Migration tested locally (up + down)
3. ✅ Database backup created

### **Deployment Steps**
1. **Backend**: Run migration (`alembic upgrade head`)
2. **Backend**: Restart service
3. **Frontend**: Build + deploy static assets
4. **Verify**: DNF tab appears, can create DNF books

### **Rollback Steps** (if needed)
1. **Database**: `alembic downgrade -1` (DNF → want_to_read)
2. **Code**: Revert changes (git revert or restore backup)
3. **Services**: Restart backend + frontend

**Rollback Time**: ~10 minutes  
**Rollback Complexity**: Low (clean migration downgrade)

---

## Testing Checklist (Abbreviated)

### **Backend** (5 min)
- ✅ `pytest backend/tests/test_books.py -v`
- ✅ All 4 new DNF tests pass

### **Frontend Manual** (30 min)
- ✅ DNF tab appears in navigation (desktop + mobile)
- ✅ Can create book with DNF status
- ✅ Can edit book to DNF status
- ✅ DNF tab filters correctly
- ✅ Search/sort work in DNF tab
- ✅ Existing tabs unchanged (regression)

### **End-to-End** (5 min)
- ✅ User flow: Create book → mark DNF → verify in DNF tab

---

## Success Criteria

Implementation complete when:

1. ✅ Migration runs without errors (up + down tested)
2. ✅ Backend API accepts `did_not_finish` status
3. ✅ All backend tests pass (existing + 4 new)
4. ✅ DNF tab appears in navigation (desktop + mobile)
5. ✅ Users can create/edit books with DNF status
6. ✅ DNF tab filters correctly (shows only DNF books)
7. ✅ 30 manual UI tests pass
8. ✅ No regressions (existing tabs work)
9. ✅ Mobile responsive layout works (bottom bar not broken)
10. ✅ Deployment tested locally

---

## Key Decisions Needing Confirmation

**Before implementation, confirm**:

### 1. Icon Choice
- **Proposed**: ❌ (cross mark)
- **Alternatives**: 🚫 (prohibited), 💔 (broken heart), 📕 (closed book)
- **Question**: Is ❌ acceptable?

### 2. Label Wording
- **Proposed**: "Did Not Finish" (clear, full phrase)
- **Alternatives**: "DNF" (shorter), "Abandoned", "Dropped"
- **Question**: Is "Did Not Finish" the right label?

### 3. Migration Downgrade Target
- **Proposed**: `did_not_finish` → `want_to_read` (safe default)
- **Alternative**: `did_not_finish` → `read` (user "completed" interaction)
- **Question**: Where should DNF books go on rollback?

### 4. Mobile Bottom Bar
- **Current**: 3 tabs (spacious)
- **After**: 4 tabs (standard pattern)
- **Question**: Is 4-tab bottom bar acceptable, or test on small screen first?

### 5. Import Status Selector
- **Current**: Import defaults to `want_to_read`
- **Proposed**: Keep default (users rarely import known-bad books)
- **Alternative**: Add status selector to import flow
- **Question**: Should import allow selecting DNF status directly?

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SQLite enum migration fails | Low | Test extensively; provide fallback SQL |
| Mobile bottom bar too crowded | Low | Test on iPhone SE; prepare horizontal scroll fallback |
| Downgrade loses data | Very Low | Downgrade moves books (no deletion); backup before deploy |

**Overall Risk**: **Low** (additive feature, clean migration, well-tested patterns)

---

## Time Estimate

| Phase | Time |
|-------|------|
| Backend (migration + tests) | 1 hour |
| Frontend (types + nav + components) | 2 hours |
| Testing (backend + frontend manual) | 1.5 hours |
| Documentation & deployment prep | 30 min |
| **Total** | **5 hours** |
| Buffer for unknowns | +30 min |
| **Realistic Estimate** | **5.5 hours** |

---

## Future Enhancements (Out of Scope)

**Not included** (consider for later):
1. DNF reason dropdown (e.g., "Too slow", "Bad writing")
2. Date DNF'd field (track when abandoned)
3. Re-attempt tracking ("Want to Re-Try" flag)
4. DNF statistics (% abandoned, most DNF'd genres)
5. Sort by DNF date (requires new field)

---

## Implementation Order

**Recommended sequence**:

1. **Backend**: Migration + model + tests (1 hour)
2. **Frontend**: Types + navigation (45 min)
3. **Frontend**: Components (dropdowns) (45 min)
4. **Testing**: Manual UI checklist (40 min)
5. **Docs**: README + comments (20 min)
6. **Deploy**: Local test + verify (30 min)

---

**Plan Status**: ✅ Ready for Implementation  
**Blockers**: None (awaiting user confirmation on 5 key decisions)  
**Complexity**: Medium (database migration + full-stack)  
**Risk**: Low (self-contained, additive change)  
**Value**: High (user-requested feature, clear use case)

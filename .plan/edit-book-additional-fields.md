# Implementation Plan: Add Publisher, Year, Page Count, and Genre to Edit Book Dialog

## Overview
Extend the Edit Book Dialog (`BookDrawer.svelte`) to allow users to edit publisher, year, page count, and genre fields. These fields currently exist in the backend model and schema but are only displayed as read-only metadata in the drawer.

## Current State Analysis

### Backend (Already Complete ✅)
- **Model** (`backend/app/models.py`): Book model already has all required fields:
  - `publisher: Optional[str]` (line 30)
  - `published_year: Optional[int]` (line 31)
  - `page_count: Optional[int]` (line 32)
  - `genre: Optional[str]` (line 33)

- **Schemas** (`backend/app/schemas.py`):
  - `BookCreate` includes all fields (lines 15-18)
  - `BookUpdate` includes all fields (lines 31-34)
  - `BookRead` includes all fields (lines 68-71)

- **API**: The `/api/books/{id}` PATCH endpoint already accepts these fields via `BookUpdate` schema

### Frontend (Needs Changes)

#### Current Implementation
- **BookDrawer.svelte** (lines 216-224):
  - Publisher, year, page count, genre, and ISBN are displayed as **read-only metadata**
  - Only title, author, status, rating, dates, notes, and cover are editable

- **TypeScript types** (`frontend/src/lib/types.ts`):
  - `Book` interface already includes all fields (lines 9-12)

#### What Needs to Change
The BookDrawer component needs to:
1. Add editable form fields for publisher, year, page count, and genre
2. Include these fields in the state management
3. Send these fields in the update payload

## Implementation Strategy

### Phase 1: Frontend - Add Editable Fields to BookDrawer

#### Changes to `BookDrawer.svelte`

**1. Add State Variables (after line 41)**
```typescript
let publisher = $state('');
let published_year = $state<number | null>(null);
let page_count = $state<number | null>(null);
let genre = $state('');
```

**2. Initialize State in $effect (lines 43-58)**
Update the effect to initialize the new fields:
```typescript
$effect(() => {
    if (book) {
        title = book.title;
        author = book.author ?? '';
        notes = book.notes ?? '';
        rating = book.rating;
        reading_status = book.reading_status;
        date_started = toDateInputValue(book.date_started);
        date_finished = toDateInputValue(book.date_finished);
        cover_url = book.cover_url ?? null;
        publisher = book.publisher ?? '';
        published_year = book.published_year;
        page_count = book.page_count;
        genre = book.genre ?? '';
        confirmDelete = false;
        dateConflictOpen = false;
        pendingStatus = null;
        pendingPayload = null;
    }
});
```

**3. Update `buildNonStatusPayload` Function (lines 60-75)**
Include the new fields in the payload:
```typescript
function buildNonStatusPayload(includeDates: boolean): Partial<Book> {
    const payload: Partial<Book> = {
        title,
        author: author || null,
        notes: notes || null,
        rating,
        cover_url: cover_url || null,
        publisher: publisher || null,
        published_year: published_year,
        page_count: page_count,
        genre: genre || null
    };

    if (includeDates) {
        payload.date_started = fromDateInputValue(date_started);
        payload.date_finished = fromDateInputValue(date_finished);
    }

    return payload;
}
```

**4. Remove Read-Only Meta Section (lines 215-224)**
Delete the current read-only metadata display section entirely.

**5. Add Editable Form Fields (after line 236, between author and status)**
Add the new form controls in a logical order:
```svelte
<label class="form-control">
    <span class="label label-text">{$_('book.publisher')}</span>
    <input class="input input-bordered input-sm" bind:value={publisher} />
</label>

<label class="form-control">
    <span class="label label-text">{$_('book.published_year')}</span>
    <input 
        type="number" 
        class="input input-bordered input-sm" 
        bind:value={published_year}
        min="0"
        max="9999"
        placeholder="YYYY"
    />
</label>

<label class="form-control">
    <span class="label label-text">{$_('book.page_count')}</span>
    <input 
        type="number" 
        class="input input-bordered input-sm" 
        bind:value={page_count}
        min="0"
        placeholder={$_('book.pages')}
    />
</label>

<label class="form-control">
    <span class="label label-text">{$_('book.genre')}</span>
    <input class="input input-bordered input-sm" bind:value={genre} />
</label>
```

**6. (Optional) Add ISBN Field**
Consider also making ISBN editable if users need to correct it:
```svelte
<label class="form-control">
    <span class="label label-text">{$_('book.isbn')}</span>
    <input class="input input-bordered input-sm" bind:value={isbn} />
</label>
```
Note: This requires adding `let isbn = $state('');` and initializing it in the $effect.

### Phase 2: Internationalization (i18n)

**Check/Add Translation Keys**
Verify that the following translation keys exist in the i18n files:
- `book.publisher`
- `book.published_year` (or `book.year`)
- `book.page_count` (or reuse `book.pages`)
- `book.genre`
- `book.isbn` (already exists, line 222)

If missing, add them to the translation files (likely in `frontend/src/lib/i18n/...`).

### Phase 3: Testing

#### Manual Testing Checklist
1. **Field Initialization**
   - Open edit drawer for a book with all metadata populated
   - Verify all fields are correctly initialized
   - Open edit drawer for a book with null/missing metadata
   - Verify fields show empty/placeholder values

2. **Field Editing**
   - Edit publisher (text field)
   - Edit year (number, validate min/max)
   - Edit page count (number, validate positive)
   - Edit genre (text field)
   - Save and verify changes persist

3. **Edge Cases**
   - Enter invalid year (e.g., -1, 10000)
   - Enter invalid page count (e.g., -50)
   - Leave fields empty and save (should set to null)
   - Change multiple fields simultaneously

4. **Status Transition + Metadata**
   - Change reading status AND edit new fields
   - Verify both status and metadata are saved
   - Test with date conflict scenarios

5. **State Persistence**
   - Edit fields, close drawer (via X button)
   - Reopen drawer and verify fields reset to original values
   - Edit fields, save successfully
   - Verify drawer closes and book list updates

6. **Responsive Layout**
   - Test on mobile viewport (320px)
   - Test on tablet viewport (768px)
   - Verify form scrolls properly with new fields

#### Automated Testing Strategy

**Option 1: Vitest Unit Tests**
Create `frontend/src/lib/components/BookDrawer.test.ts`:
```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import BookDrawer from './BookDrawer.svelte';
import type { Book } from '$lib/types';

describe('BookDrawer - Additional Fields', () => {
    const mockBook: Book = {
        id: 1,
        title: 'Test Book',
        author: 'Test Author',
        publisher: 'Test Publisher',
        published_year: 2023,
        page_count: 300,
        genre: 'Science Fiction',
        isbn: '978-1234567890',
        // ... other required fields
    };

    it('should display editable publisher field', async () => {
        const { component } = render(BookDrawer, {
            props: { book: mockBook, open: true }
        });
        
        const publisherInput = screen.getByLabelText(/publisher/i);
        expect(publisherInput).toBeInTheDocument();
        expect(publisherInput).toHaveValue('Test Publisher');
    });

    it('should display editable year field', async () => {
        // Test year field initialization and editing
    });

    it('should display editable page count field', async () => {
        // Test page count field initialization and editing
    });

    it('should display editable genre field', async () => {
        // Test genre field initialization and editing
    });

    it('should include new fields in save payload', async () => {
        const mockSave = vi.fn();
        // Test that save includes all new fields
    });

    it('should handle null values for optional fields', async () => {
        const bookWithoutMetadata = { ...mockBook, publisher: null, published_year: null, page_count: null, genre: null };
        // Test null handling
    });
});
```

**Option 2: Playwright E2E Tests**
If E2E testing infrastructure exists, create tests for:
1. Full edit workflow with new fields
2. Save and verify persistence
3. Field validation
4. Cross-browser compatibility

**Recommended Approach**: Start with manual testing checklist, then add Vitest unit tests for component behavior.

## Implementation Order

### Step 1: Update BookDrawer Component (30 min)
1. Add state variables
2. Update $effect initialization
3. Update buildNonStatusPayload
4. Remove read-only meta section
5. Add editable form fields

### Step 2: Verify i18n (10 min)
1. Check existing translation keys
2. Add missing keys if needed

### Step 3: Manual Testing (30 min)
1. Run through manual testing checklist
2. Test in different viewports
3. Verify API calls send correct data

### Step 4: Write Tests (Optional, 45 min)
1. Create Vitest test file
2. Implement unit tests for new fields
3. Run test suite

## Files to Modify

### Required Changes
- `frontend/src/lib/components/BookDrawer.svelte` - Add editable fields
- `frontend/src/lib/i18n/...` - Verify/add translation keys (if needed)

### Test Files to Create (Optional)
- `frontend/src/lib/components/BookDrawer.test.ts` - Unit tests

## Risk Assessment

### Low Risk ✅
- Backend already supports these fields
- API schema already handles them
- TypeScript types already defined
- No database migrations needed

### Potential Issues
1. **Translation keys**: May need to add missing i18n keys
2. **Layout spacing**: New fields might make drawer feel cramped on mobile
3. **Input validation**: Year and page count need proper constraints
4. **Field ordering**: Need to decide optimal form field order for UX

### Mitigation
- Review i18n files before implementation
- Test on mobile viewport (320px width)
- Use HTML5 input validation (min/max)
- Follow logical grouping: Title → Author → Publisher → Year → Pages → Genre → ISBN

## Success Criteria

✅ Users can edit publisher in the BookDrawer
✅ Users can edit published year (with validation 0-9999)
✅ Users can edit page count (with validation ≥0)
✅ Users can edit genre in the BookDrawer
✅ All fields save correctly via API
✅ Empty fields save as null in database
✅ Drawer layout remains clean and scrollable
✅ Fields reset properly when drawer is closed and reopened
✅ Changes are reflected in book list after save
✅ Manual testing checklist passes

## Questions for Review

1. **ISBN Editability**: Should ISBN also become editable, or remain fixed after import?
   - Recommendation: Make it editable for correction of typos
   
2. **Field Grouping**: Should metadata fields be grouped visually (e.g., "Book Details" section)?
   - Recommendation: Use a simple linear form without explicit grouping
   
3. **Year Input**: Should we use a text input or number input for year?
   - Recommendation: Number input with min/max validation

4. **Genre Input**: Should genre be a text field or dropdown/autocomplete?
   - Recommendation: Start with text field, consider autocomplete in future if genre taxonomy emerges

## Estimated Time
- Implementation: 40-60 minutes
- Testing: 30-45 minutes
- **Total: 1.5-2 hours**

## Approval Required
Please review this plan and provide feedback:
- **✅ I'm fine, please start implementation** - Proceed with the plan as-is
- **🔄 Plan needs changes** - Specify what needs adjustment
- **❌ Thanks, do nothing** - Cancel this feature

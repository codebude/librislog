# Implementation Plan: Top 3 Authors with Overlapping Cover Images

## Overview

**Goal:** Replace the single "Favorite Author" section on the statistics page with "Top 3 Authors", maintaining the cover gallery but with overlapping images to save screen space.

**Current Implementation:**
- Backend: `/api/statistics` returns `favorite_author: FavoriteAuthor | null`
- `FavoriteAuthor` schema contains: `author`, `book_count`, `cover_urls` (list of strings, max 20)
- Frontend: Displays single author card with book count and horizontal cover gallery (h-28, gap-2)
- Uses i18n key: `statistics.favoriteAuthor`

**Desired State:**
- Backend: Return `top_authors: list[TopAuthor]` (max 3 items)
- Each `TopAuthor` contains: `author`, `book_count`, `cover_urls` (list of strings, up to 5 covers per author)
- If author has more than 5 books/cover_urls, visually hint, that there are more than 5 books.
- Frontend: Display 3 author cards in a responsive grid, each with overlapping cover images
- Update i18n keys: `statistics.topAuthors`, `statistics.top3Authors`

---

## 1. Data Model & Schema Changes

### 1.1 Backend Schema (`backend/app/schemas.py`)

**Actions:**
- Rename `FavoriteAuthor` → `TopAuthor` (or keep both during migration)
- Keep fields: `author: str`, `book_count: int`, `cover_urls: list[str]`
- Update `StatisticsResponse`:
  - Remove: `favorite_author: Optional[FavoriteAuthor]`
  - Add: `top_authors: list[TopAuthor]` (max 3 elements)

**Decision:** Use a list instead of separate fields to keep the schema clean and extensible.

**Edge Cases:**
- If user has 0-2 authors, return what's available (don't pad with nulls)
- Empty library: return `top_authors: []`

---

## 2. Backend Query & Logic Changes

### 2.1 Statistics Endpoint (`backend/app/routers/statistics.py`)

**Current Logic (lines 301-327):**
```python
author_counts: Counter[str] = Counter()
for book in books:
    if book.author and book.author.strip():
        author_counts[book.author.strip()] += 1

favorite_author = None
if author_counts:
    author_name, author_count = min(
        author_counts.items(),
        key=lambda item: (-item[1], item[0].lower()),
    )
    # Fetch up to 20 cover_urls for the single author
    favorite_author = FavoriteAuthor(...)
```

**New Logic:**
1. **Count authors** (same as before, using `Counter`)
2. **Sort by count descending, then alphabetically** (same logic)
3. **Take top 3** using `most_common(3)` or manual slicing
4. **For each of the top 3 authors:**
   - Query database for distinct cover URLs (limit 5 per author to save response size)
   - Construct `TopAuthor` object
5. Return `top_authors: list[TopAuthor]`

**Query Optimization:**
- Current: Single SQL query for 1 author's covers (limit 20)
- New: 3 SQL queries (one per author, limit 5 each) = 15 covers max total
- **Alternative (batch query):** Use `WHERE author IN (...)` to fetch all in one query, then partition by author in Python
  - **Recommended:** Batch query for better performance

**Pseudocode:**
```python
top_authors = []
if author_counts:
    top_3 = author_counts.most_common(3)
    author_names = [name for name, _ in top_3]
    
    # Batch fetch covers for all 3 authors
    cover_rows = session.exec(
        select(Book.author, Book.cover_url)
        .where(
            Book.user_id == current_user.id,
            Book.author.in_(author_names),
            Book.cover_url.is_not(None),
        )
        .distinct()
    ).all()
    
    # Group by author, limit 5 per author
    author_covers: dict[str, list[str]] = {name: [] for name in author_names}
    for author, cover_url in cover_rows:
        if len(author_covers[author]) < 5:
            author_covers[author].append(cover_url)
    
    # Build response
    for author_name, book_count in top_3:
        top_authors.append(TopAuthor(
            author=author_name,
            book_count=book_count,
            cover_urls=author_covers.get(author_name, []),
        ))
```

**Considerations:**
- **Books without authors:** Excluded (same as current behavior)
- **Cover limit per author:** 5 (reduced from 20 for single author)
  - Rationale: 3 authors × 5 covers = 15 total (vs 20 for single author)
- **Sorting:** Deterministic (by count desc, then alphabetical for ties)

---

## 3. Frontend Type Changes

### 3.1 TypeScript Types (`frontend/src/lib/types.ts`)

**Actions:**
- Rename `FavoriteAuthor` → `TopAuthor` (or alias during migration)
- Update `StatisticsResponse`:
  - Remove: `favorite_author: FavoriteAuthor | null;`
  - Add: `top_authors: TopAuthor[];`

**Example:**
```typescript
export interface TopAuthor {
    author: string;
    book_count: number;
    cover_urls: string[];
}

export interface StatisticsResponse {
    // ... other fields
    top_authors: TopAuthor[];  // replaces favorite_author
}
```

---

## 4. Frontend UI Changes

### 4.1 Statistics Page (`frontend/src/routes/statistics/+page.svelte`)

**Current Implementation (lines 317-334):**
- Single card with title "Favorite Author"
- Author name (text-lg, font-semibold)
- Book count (text-sm, muted)
- Horizontal cover gallery: `flex items-end gap-2 overflow-x-auto`
- Cover images: `h-28 w-auto rounded shadow-sm`

**New Implementation:**

#### Layout Options:
**Option A: Vertical Stack (Mobile-First)**
- 3 cards stacked vertically
- Each card: author name, count, overlapping covers
- Responsive: Same on all screen sizes

**Option B: Responsive Grid**
- Mobile: Vertical stack (1 column)
- Tablet: 2 columns (top 2 authors in first row, 3rd alone)
- Desktop: 3 columns

**Recommendation:** Option B (responsive grid) for better space usage on larger screens.

#### Overlapping Cover Design:

**Implementation Strategy:**
- Container: `flex items-end` (no gap, use negative margin instead)
- Each cover: `-ml-3` (except first one) to create overlap
- Z-index: Increase per image (`:nth-child(1)` z-10, `:nth-child(2)` z-20, etc.)
- Shadow: Add `shadow-md` or `ring-2 ring-white` to create separation between overlapping images
- Height: Keep `h-28` (consistent with current design)

**Alternative Strategy (Using CSS Grid):**
- Container: `grid grid-cols-[repeat(auto-fit,80px)]` with `gap-0`
- Each image: `col-start-1` (all in same column) + transform offset
- More complex but better for dynamic cover counts

**Recommendation:** Negative margin approach (simpler, matches existing patterns in codebase).

**Example Markup:**
```svelte
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {#each stats.top_authors as author, idx}
        <div class="card bg-base-100 border border-base-200 shadow-sm">
            <div class="card-body gap-3">
                <div class="flex items-baseline gap-2">
                    <span class="badge badge-sm badge-primary">{idx + 1}</span>
                    <h3 class="font-semibold text-lg">{author.author}</h3>
                </div>
                <div class="text-sm text-base-content/70">
                    {$_('statistics.booksCount', { values: { count: author.book_count } })}
                </div>
                {#if author.cover_urls.length > 0}
                    <div class="flex items-end">
                        {#each author.cover_urls.slice(0, 5) as url, coverIdx}
                            <img
                                src={url}
                                alt={$_('book.cover')}
                                class="h-28 w-auto rounded shadow-md {coverIdx > 0 ? '-ml-3' : ''}"
                                style="z-index: {coverIdx + 1};"
                            />
                        {/each}
                    </div>
                {:else}
                    <p class="text-xs text-base-content/50">{$_('statistics.noCovers')}</p>
                {/if}
            </div>
        </div>
    {/each}
</div>
```

**UI Enhancements:**
- Add rank badge (1, 2, 3) for visual hierarchy
- Use primary color for badge to match existing design system
- Limit displayed covers to 5 (even if backend sends more)
- Handle no covers gracefully (show placeholder text)

**Responsive Considerations:**
- Mobile (<768px): 1 column, full width cards
- Tablet (768px-1024px): 2 columns
- Desktop (>1024px): 3 columns
- Overlapping covers work on all screen sizes (fixed height h-28)
- Test overflow: If author has 5 covers, total width ≈ 1 cover + 4×(overlap) = reasonable

---

## 5. Internationalization (i18n)

### 5.1 Update Translation Keys

**Files to Modify:**
- `frontend/src/lib/i18n/locales/en.json`
- `frontend/src/lib/i18n/locales/de.json` (if exists)

**Changes:**

**Option A: Replace existing key**
```json
// Before:
"favoriteAuthor": "Favorite Author"

// After:
"topAuthors": "Top 3 Authors"
```

**Option B: Add new key, deprecate old one**
```json
"favoriteAuthor": "Favorite Author",  // deprecated, remove after migration
"topAuthors": "Top 3 Authors",
"top3Authors": "Top 3 Authors"  // alternative phrasing
```

**Additional Keys (if needed):**
```json
"noCovers": "No covers available"
```

**Recommendation:** Option A (clean replacement) since this is a breaking change anyway.

---

## 6. Testing Strategy

### 6.1 Backend Tests (`backend/tests/test_statistics.py`)

**Existing Test to Update:**
- `test_statistics_core_metrics_and_distributions` (lines 46-121)
  - Currently asserts: `data["favorite_author"]["author"] == "Author A"`
  - Update to assert: `len(data["top_authors"]) == 3` (or less if fewer authors)
  - Assert ordering: `data["top_authors"][0]["author"] == "Author A"` (highest count)
  - Assert cover URLs presence for each author

**New Tests to Add:**

1. **`test_statistics_top_authors_ordering`**
   - Create 5 authors with different book counts
   - Assert top 3 are returned in descending order by count
   - Assert alphabetical ordering for ties

2. **`test_statistics_top_authors_with_two_authors`**
   - Create only 2 authors
   - Assert `len(top_authors) == 2` (no padding to 3)

3. **`test_statistics_top_authors_empty_library`**
   - No books in library
   - Assert `top_authors == []`

4. **`test_statistics_top_authors_cover_limit`**
   - Create author with 10 books (all with covers)
   - Assert each author has max 5 cover URLs

5. **`test_statistics_top_authors_no_covers`**
   - Create authors with books but no cover URLs
   - Assert `cover_urls == []` for all authors

6. **`test_statistics_top_authors_excludes_books_without_author`**
   - Create books with empty/null author field
   - Assert they don't appear in top_authors

### 6.2 Frontend Testing

**Manual Testing Checklist:**

1. **Desktop (>1024px):**
   - [ ] 3 author cards displayed in 3-column grid
   - [ ] Rank badges (1, 2, 3) visible
   - [ ] Overlapping covers render correctly (no clipping, proper z-index)
   - [ ] Shadow/ring separation visible between overlapping images
   - [ ] No horizontal scroll

2. **Tablet (768px-1024px):**
   - [ ] 2-column grid (top 2 authors in row 1, 3rd author in row 2)
   - [ ] Cards maintain aspect ratio
   - [ ] Overlapping covers still work

3. **Mobile (<768px):**
   - [ ] Single column layout
   - [ ] Cards stack vertically
   - [ ] Overlapping covers readable (not too squished)
   - [ ] Touch-friendly spacing

4. **Edge Cases:**
   - [ ] 0 authors: Show empty state or hide section
   - [ ] 1 author: Show single card (no empty cards)
   - [ ] 2 authors: Show 2 cards
   - [ ] Author with 0 covers: Show "No covers" placeholder
   - [ ] Author with 1 cover: No overlap, single image
   - [ ] Author with 5 covers: All 5 visible with overlap

5. **i18n:**
   - [ ] English: "Top 3 Authors" displays correctly
   - [ ] German (if applicable): Translation loads
   - [ ] Book count pluralization works: "1 book" vs "3 books"

**Automated Tests (if test framework exists):**
- Component test for overlapping cover layout
- Snapshot test for responsive grid
- API mock test with 0, 1, 2, 3 authors

---

## 7. Migration & Rollout Strategy

### 7.1 Deployment Approach

**Option A: Breaking Change (Recommended)**
- Deploy backend + frontend together (coordinated release)
- Backend change: Remove `favorite_author`, add `top_authors`
- Frontend change: Update UI to consume `top_authors`
- Risk: If frontend deploys first (before backend), it will break temporarily

**Option B: Backward-Compatible Migration (2-Phase)**
- **Phase 1:** Backend returns BOTH `favorite_author` and `top_authors`
  - Frontend still uses `favorite_author` (no change yet)
- **Phase 2:** Frontend switches to `top_authors`
  - Backend removes `favorite_author` field
- Risk: More complex, but safer for staged rollouts

**Recommendation:** Option A (coordinated deployment) since this is a single-user app with Docker deployment.

### 7.2 Rollback Plan

**If issues arise after deployment:**
1. Git revert the commits (backend + frontend)
2. Rebuild Docker images
3. Redeploy

**Pre-Deployment Validation:**
- Run backend tests: `uv run pytest backend/tests/test_statistics.py`
- Manual test frontend in development mode
- Check i18n keys loaded correctly

### 7.3 Data Migration

**No database migration needed** — This is a view-only change (query logic change, no schema change).

---

## 8. Edge Cases & Risk Analysis

### 8.1 Edge Cases

| Scenario | Expected Behavior | Mitigation |
|----------|-------------------|------------|
| User has 0 books | `top_authors: []` | Hide section or show empty state |
| User has 1 author | `top_authors: [author1]` | Display single card (responsive grid handles this) |
| User has 2 authors | `top_authors: [author1, author2]` | Display 2 cards |
| Tie in book count | Alphabetical sort (case-insensitive) | Already implemented in existing code |
| Author with no covers | `cover_urls: []` | Show "No covers available" text |
| Very long author name | Text wrap/truncate | Use `truncate` or `line-clamp-1` CSS |
| Extremely wide cover image | Fixed height (h-28), width auto | May cause horizontal overflow if aspect ratio extreme |
| Backend returns >3 authors (bug) | Frontend limits to first 3 | Use `.slice(0, 3)` in frontend |
| Backend returns <5 covers per author | Display what's available | No issue, overlap works with 1-5 images |

### 8.2 Performance Considerations

**Backend:**
- Current: 1 SQL query for 20 covers (single author)
- New: 1 SQL query for 15 covers (3 authors × 5 each)
- **Impact:** Slightly better (less data transferred)

**Frontend:**
- Current: Render 1 card with up to 20 images
- New: Render 3 cards with up to 5 images each (15 total)
- **Impact:** Neutral (same number of images)

**Bundle Size:**
- No new dependencies
- Minimal CSS changes
- **Impact:** Negligible

### 8.3 Accessibility Considerations

**Actions:**
- Add `alt` text to cover images: `alt={$_('book.coverOf', { values: { title: author.author } })}`
- Ensure rank badges have semantic meaning (use `<span class="badge">` with text, not just visual)
- Test keyboard navigation (tab through cards)
- Check color contrast for rank badges (primary color should be WCAG AA compliant)

### 8.4 Browser Compatibility

**Overlapping Images with Negative Margin:**
- Supported in all modern browsers (Chrome, Firefox, Safari, Edge)
- Z-index with inline styles: No issues
- Flexbox: Widely supported

**Grid Layout:**
- `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` uses Tailwind responsive prefixes
- Supported in all browsers supporting CSS Grid (IE11 would fail, but not a target)

---

## 9. Implementation Checklist

### Phase 1: Backend Changes
- [ ] Update schema in `backend/app/schemas.py`
  - [ ] Create `TopAuthor` class (or rename `FavoriteAuthor`)
  - [ ] Update `StatisticsResponse` to use `top_authors: list[TopAuthor]`
- [ ] Update query logic in `backend/app/routers/statistics.py`
  - [ ] Modify author counting to return top 3
  - [ ] Implement batch cover fetching (5 covers per author)
  - [ ] Update return statement to use `top_authors`
- [ ] Update backend tests in `backend/tests/test_statistics.py`
  - [ ] Fix existing test assertions (replace `favorite_author` with `top_authors[0]`)
  - [ ] Add new tests (ordering, edge cases, cover limits)
- [ ] Run tests: `uv run pytest backend/tests/test_statistics.py -v`

### Phase 2: Frontend Changes
- [ ] Update types in `frontend/src/lib/types.ts`
  - [ ] Rename `FavoriteAuthor` → `TopAuthor`
  - [ ] Update `StatisticsResponse` interface
- [ ] Update UI in `frontend/src/routes/statistics/+page.svelte`
  - [ ] Replace favorite author card with responsive grid (3 cards)
  - [ ] Implement overlapping cover layout with negative margin
  - [ ] Add rank badges (1, 2, 3)
  - [ ] Handle edge cases (0, 1, 2 authors)
- [ ] Update i18n in `frontend/src/lib/i18n/locales/*.json`
  - [ ] Replace `"favoriteAuthor"` with `"topAuthors"`
  - [ ] Add `"noCovers"` key (if needed)
  - [ ] Update German translation (if applicable)
- [ ] Manual testing
  - [ ] Desktop: 3-column grid, overlapping covers
  - [ ] Tablet: 2-column grid
  - [ ] Mobile: 1-column stack
  - [ ] Edge cases: 0, 1, 2 authors; no covers; long names

### Phase 3: Deployment
- [ ] Update `.plan/53-top-3-authors-with-overlapping-covers.md` with actual implementation notes
- [ ] Commit backend changes
- [ ] Commit frontend changes
- [ ] Build and test locally: `docker compose up --build`
- [ ] Validate statistics page in browser
- [ ] Deploy to production
- [ ] Monitor for errors (check browser console, backend logs)

---

## 10. Open Questions & Decisions

### Decision Log:

1. **Q: Should we keep `FavoriteAuthor` schema name or rename to `TopAuthor`?**
   - **A:** Rename to `TopAuthor` for semantic clarity.

2. **Q: How many covers per author?**
   - **A:** 5 covers per author (max 15 total), down from 20 for single author.

3. **Q: Should we show rank badges?**
   - **A:** Yes, adds visual hierarchy and makes "top 3" concept clear.

4. **Q: What if user has <3 authors?**
   - **A:** Show what's available (1 or 2 cards), don't pad with empty cards.

5. **Q: Grid layout or always vertical stack?**
   - **A:** Responsive grid (1/2/3 columns based on screen size).

6. **Q: Overlapping method?**
   - **A:** Negative margin (`-ml-3`) with inline z-index.

7. **Q: Should we fetch covers in batch or 3 separate queries?**
   - **A:** Batch query (`WHERE author IN (...)`) for better performance.

8. **Q: Do we need to support old API response during rollout?**
   - **A:** No, coordinated deployment (breaking change acceptable for single-user app).

---

## 11. Related Files

### Backend:
- `backend/app/schemas.py` — Schema definitions
- `backend/app/routers/statistics.py` — Statistics endpoint logic
- `backend/tests/test_statistics.py` — Backend tests

### Frontend:
- `frontend/src/lib/types.ts` — TypeScript interfaces
- `frontend/src/routes/statistics/+page.svelte` — Statistics page UI
- `frontend/src/lib/i18n/locales/en.json` — English translations
- `frontend/src/lib/i18n/locales/de.json` — German translations

### Documentation:
- `README.md` — May need update if statistics features are documented
- `.plan/46-statistics-page.md` — Original statistics page plan (reference only)

---

## 12. Success Criteria

✅ **Backend:**
- `/api/statistics` returns `top_authors: list[TopAuthor]` with up to 3 authors
- Authors sorted by book count (descending), then alphabetically
- Each author has up to 5 cover URLs
- All existing tests pass + new tests added

✅ **Frontend:**
- Statistics page displays 3 author cards in responsive grid
- Cover images overlap correctly with visible separation (shadow/ring)
- Rank badges (1, 2, 3) displayed
- Works on mobile, tablet, desktop
- i18n key updated to "Top 3 Authors"

✅ **Quality:**
- No console errors
- No visual regressions on other statistics components
- Accessible (keyboard nav, alt text, color contrast)
- No performance degradation

---

## Timeline Estimate

| Task | Estimated Time |
|------|----------------|
| Backend schema + query changes | 30 min |
| Backend tests (update + new) | 45 min |
| Frontend types + UI changes | 60 min |
| i18n updates | 10 min |
| Manual testing (responsive, edge cases) | 30 min |
| Code review & polish | 15 min |
| **Total** | **~3 hours** |

---

## Notes

- This is a **view-only change** — no database schema modification required
- The overlapping cover design is similar to common UI patterns (e.g., user avatars in group notifications)
- Consider adding hover effect to overlapping covers (slight lift/scale on hover) for polish
- If performance becomes an issue with 3 SQL queries per statistics request, consider caching the result (low priority for single-user app)
- Future enhancement: Make the number of top authors configurable (user setting), but out of scope for this plan

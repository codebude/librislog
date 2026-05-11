# Summary: ISBN Barcode Scanner for Import Dialog

## Quick Overview

Add a camera-based barcode scanner to the Import tab that detects ISBN barcodes and automatically triggers import search, eliminating manual ISBN entry on mobile and desktop.

---

## What's Being Built

**Feature**: Camera barcode scanner button in Import tab that:
- Opens camera view in a modal
- Detects ISBN barcodes (EAN-13, UPC-A, etc.)
- Auto-populates search input + triggers search
- Works on mobile (rear camera + flashlight) and desktop (webcam)

**User Flow**:
1. Click "📷" button in Import tab
2. Position book barcode in camera frame
3. Barcode detected → modal closes → search runs automatically
4. Results appear → user clicks "Add"

---

## Implementation Approach

### **Component Architecture**

**New component**: `BarcodeScanner.svelte`
- Encapsulates scanner logic
- Props: `open` (bindable), `onDetected` (callback)
- Lifecycle: start/stop scanner on open/close, cleanup on destroy
- Uses `html5-qrcode` library (Apache-2.0, 45KB gzipped)

**Integration**: `ImportSearch.svelte`
- Add scanner button (📷 icon, `btn-outline btn-sm`)
- Add `<BarcodeScanner>` component at end
- Handle detection: set `searchType = 'isbn'`, populate `query`, call `search()`

### **Library Choice: `html5-qrcode`**

**Why this library**:
- ✅ 11k+ stars, actively maintained (2024)
- ✅ Built-in camera UI (torch, camera selector)
- ✅ Supports ISBN formats (EAN-13, EAN-8, UPC-A, UPC-E, CODE-128)
- ✅ Mobile + desktop support, TypeScript definitions
- ✅ Native BarcodeDetector API fallback (faster)
- ✅ Proven in production (TiddlyWiki, Frappe, NocoBase)

**Configuration**:
```typescript
const config = {
    fps: 10,
    qrbox: { width: 300, height: 150 }, // Wide rectangle for barcodes
    formatsToSupport: [
        Html5QrcodeSupportedFormats.EAN_13,  // ISBN-13
        Html5QrcodeSupportedFormats.EAN_8,   // ISBN-8
        Html5QrcodeSupportedFormats.UPC_A,   // US books
        Html5QrcodeSupportedFormats.UPC_E,   // Compact UPC
        Html5QrcodeSupportedFormats.CODE_128 // Fallback
    ],
    showTorchButtonIfSupported: true, // Flashlight on mobile
    rememberLastUsedCamera: true,     // Rear camera on mobile
    useBarCodeDetectorIfSupported: true // Native API (faster)
};
```

---

## Key Files Modified

| File | Changes |
|------|---------|
| `frontend/package.json` | Add `html5-qrcode` dependency |
| `frontend/src/lib/components/BarcodeScanner.svelte` | **NEW**: Scanner component (~200 lines) |
| `frontend/src/lib/components/ImportSearch.svelte` | • Add scanner button<br>• Add `<BarcodeScanner>` component<br>• Add `handleBarcodeDetected()` function<br>(~25 lines added) |

**Total new code**: ~225 lines + 45KB library

---

## Scanner UX Flow

### **Success Path**
1. User clicks "📷 Scan Barcode" button
2. Browser prompts for camera permission (first use)
3. Camera view appears in modal (16:9 aspect ratio)
4. User positions book barcode in scanning region (wide rectangle)
5. Barcode detected → toast "Scanned ISBN: 9780441013593"
6. Modal closes → search input shows ISBN → search runs automatically
7. Results appear → user clicks "Add to Want to Read"

### **Error Paths**

| Error | UX Handling |
|-------|-------------|
| Camera permission denied | Alert: "Camera access denied. Please allow in settings or enter ISBN manually." |
| No camera available | Toast: "No camera found. Please enter ISBN manually." + button hidden |
| Invalid barcode scanned | Toast: "Invalid ISBN scanned. Try again or enter manually." + no auto-search |
| Scanner fails to initialize | Alert: Generic error message + modal closes |
| Poor lighting / damaged barcode | User can enable torch (mobile) or manually enter ISBN |

---

## Mobile & Desktop Support

### **Mobile Optimizations**
- **Rear camera**: Prefer `facingMode: "environment"` (book scanning)
- **Torch button**: Enabled on supported devices (flashlight)
- **Responsive modal**: Full-height on small screens
- **Touch targets**: Large close button (44×44 px minimum)
- **Performance**: 10 FPS (balance speed vs. battery)

### **Desktop Optimizations**
- **Webcam selection**: Dropdown if multiple cameras available
- **Larger scanner region**: 400×200 px (vs. 300×150 on mobile)
- **Keyboard shortcuts**: Escape key to close modal
- **Performance**: Native BarcodeDetector API (faster on Chrome)

### **Browser Compatibility**

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome 90+ | ✅ Full | Best performance, native BarcodeDetector |
| Safari 14+ | ✅ Full | iOS 14+ required |
| Firefox 88+ | ✅ Full | Slightly slower detection |
| Edge 90+ | ✅ Full | Chromium-based |
| IE11 | ❌ None | No MediaStream API (button hidden) |

---

## Testing Strategy

### **Manual Testing Checklist** (30+ tests)

**Basic Functionality** (10 tests):
1. Scanner button appears
2. Modal opens with camera view
3. Barcode detection works
4. ISBN populates search input
5. Search auto-triggers
6. Results appear correctly
7. Modal closes after scan
8. Close button works
9. Escape key works
10. Camera releases on close

**Error Handling** (5 tests):
11. Permission denied → error shown
12. No camera → button hidden or error
13. Invalid barcode → error, no search
14. Scanner init fails → error shown
15. Scanner cleanup on unmount

**Mobile-Specific** (7 tests):
16. Rear camera used by default
17. Torch button appears (if supported)
18. Torch enables flashlight
19. Portrait mode works
20. Landscape mode works
21. Modal responsive on small screens
22. Close button easily tappable

**Desktop-Specific** (4 tests):
23. Webcam selected correctly
24. Camera selector works (if multiple)
25. Escape closes modal
26. Scanner region appropriately sized

**Performance** (3 tests):
27. Detection < 3 seconds (good lighting)
28. No lag during scanning
29. Camera releases on close

**Accessibility** (3 tests):
30. Keyboard navigation works
31. Screen reader announces button
32. Focus management correct

**Devices**: Test on iPhone (Safari), Android (Chrome), macOS (Chrome/Safari), Windows (Chrome/Edge)

**Future**: Playwright tests for modal open/close (barcode simulation difficult)

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Camera permission denied | ✅ User-friendly error + fallback to manual entry |
| No camera available | ✅ Hide button or show error |
| Invalid barcode scanned | ✅ Validate ISBN, show error, don't search |
| Poor lighting / damaged barcode | ⚠️ User can retry or use torch (manual fallback) |
| Multiple barcodes in frame | ⚠️ First detected is used (known limitation) |
| Scanner stuck open (unmount) | ✅ `onDestroy` cleanup releases camera |
| Browser not supported | ✅ Hide button (feature detection) |
| Rear camera unavailable (mobile) | ✅ Fall back to front camera |
| User navigates away during scan | ✅ Scanner stops, camera released |

---

## Performance

### **Bundle Size**
- **Before**: ~150KB gzipped (SvelteKit + DaisyUI)
- **After**: ~195KB gzipped (+45KB library + ~3KB component)
- **Impact**: +30% increase

**Optimization options** (future):
1. **Lazy load** scanner library (dynamic import on button click)
2. **Code splitting** at route level (SvelteKit automatic)
3. **Tree-shake** unused formats (if library supports)

**Decision**: Accept initial increase (45KB reasonable for this feature). Implement lazy loading if load times become issue.

### **Runtime Performance**
- **CPU**: 10-20% during scanning (10 FPS video processing)
- **Memory**: 10-30 MB (video stream, released on close)
- **Battery**: Moderate drain (camera active), minimal for short scans (< 1 min)

**Mitigation**: Stop scanner immediately after detection, don't leave camera running.

---

## Success Criteria

1. ✅ Scanner button appears in Import tab
2. ✅ Modal opens with camera view
3. ✅ Barcode detected and populates search input
4. ✅ Search auto-triggers in ISBN mode
5. ✅ Works on mobile (rear camera, torch)
6. ✅ Works on desktop (webcam, keyboard shortcuts)
7. ✅ Camera permissions handled gracefully
8. ✅ Error states user-friendly
9. ✅ Scanner stops and releases camera on close
10. ✅ No performance issues (smooth 10 FPS)
11. ✅ Detection < 3 seconds (good lighting)
12. ✅ All manual tests pass on mobile + desktop

---

## Implementation Steps

| Step | Description | Time |
|------|-------------|------|
| 1 | Install `html5-qrcode` library | 5 min |
| 2 | Create `BarcodeScanner.svelte` component | 2 hours |
| 3 | Integrate into `ImportSearch.svelte` | 45 min |
| 4 | Handle edge cases (permissions, errors) | 1 hour |
| 5 | Mobile & desktop optimization | 30 min |
| 6 | Manual testing (30+ test cases) | 1.5 hours |
| 7 | Documentation (inline comments, README) | 20 min |
| **Total** | | **6.5 hours** |

**Buffer for unknowns**: +1.5 hours (API quirks, device-specific issues)

**Realistic estimate**: **8 hours** (1 full day)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Users always deny camera permission | Low | Medium | Clear value proposition; manual entry still works |
| Detection too slow (> 5 seconds) | Low | Medium | Use native BarcodeDetector API; allow manual fallback |
| Poor lighting causes failures | Medium | Low | Enable torch button; show lighting tip |
| Bundle size too large (slow load) | Low | Medium | Lazy load library on first button click |
| Library maintenance stops | Low | High | `html5-qrcode` actively maintained (2024, 11k stars); can switch to quagga2 |
| Incompatible barcodes (damaged, non-ISBN) | Medium | Low | Validate ISBN before searching; show error |

---

## Future Enhancements

1. **Bulk scanning**: Scan multiple books in sequence without closing modal
2. **Scan history**: Show recently scanned ISBNs (localStorage)
3. **Manual entry fallback**: Input field in scanner modal for damaged barcodes
4. **QR code support**: Scan book page URLs (Open Library, Goodreads)
5. **Offline detection**: Cache library for offline use (IndexedDB)
6. **Visual feedback**: Bounding box around detected barcode
7. **Auto-stop timeout**: Close scanner after 60s inactivity (battery saving)
8. **Sound/haptic feedback**: Beep or vibration on successful scan (mobile)
9. **Scanner settings**: User-configurable FPS, qrbox size, camera preference
10. **Analytics**: Track scan success rate, avg scan time (privacy-respecting)

---

## Dependencies

**New**:
- **`html5-qrcode`**: `^2.x` (Apache-2.0, ~45KB gzipped, TypeScript support)

**Existing** (no changes):
- Svelte 5, SvelteKit 2.x
- DaisyUI v5 (modal, buttons)
- Tailwind CSS v4

**Browser APIs**:
- `navigator.mediaDevices.getUserMedia()` (camera access)
- `navigator.mediaDevices.enumerateDevices()` (camera detection)
- `BarcodeDetector` API (optional, native detection)

---

## Rollback Plan

**Quick disable** (feature flag):
- Wrap scanner button in `{#if false}` → deploy hotfix (< 5 min)

**Full rollback**:
- Remove `BarcodeScanner.svelte`
- Remove scanner button from `ImportSearch.svelte`
- Uninstall `html5-qrcode`
- Rebuild + deploy (< 15 min)

**Complexity**: Low (self-contained feature)

---

## Key Decisions & User Confirmation Needed

### **Before Implementation, Confirm**:

1. **Scanner button placement**:
   - **Proposed**: Between type selector and "Search" button
   - **Alternative**: Below search bar (separate row)
   - **Question**: Is button placement acceptable, or prefer different layout?

2. **Auto-search after scan**:
   - **Proposed**: Automatically trigger search when barcode detected (faster UX)
   - **Alternative**: Populate input only, require user to click "Search"
   - **Question**: Should search auto-trigger, or let user review ISBN first?

3. **Scanner button icon**:
   - **Proposed**: Camera emoji "📷" (no icon library needed)
   - **Alternative**: Text "Scan" or SVG icon (requires icon library)
   - **Question**: Is emoji acceptable, or prefer text/icon?

4. **Bundle size trade-off**:
   - **Proposed**: Accept +45KB (html5-qrcode), lazy load later if needed
   - **Alternative**: Use lighter library (quagga2, 35KB) but requires custom UI
   - **Question**: Is +30% bundle size acceptable for this feature?

5. **Mobile camera preference**:
   - **Proposed**: Default to rear camera on mobile (book scanning)
   - **Alternative**: Let user choose camera first
   - **Question**: Should rear camera be automatic default?

---

## Context for Implementation

**When ready to implement**:
- Use **Context7** `/mebjas/html5-qrcode` for up-to-date API docs and examples
- Use **grep.app** (MCP) for real-world code examples of `Html5Qrcode` integration
- Refer to **Phase 2** in full plan for detailed `BarcodeScanner.svelte` structure
- Test ISBNs: 9780441013593 (Dune), 9780545010221 (Harry Potter), 0441013597 (ISBN-10)

**Files to reference**:
- `.plan/14-mark-imported-books-in-search.md` — Similar component pattern (modal, state management)
- `frontend/src/lib/components/ImportSearch.svelte` — Integration point
- `backend/tests/conftest.py` — Testing setup (no backend changes, but good reference)

---

**Status**: Ready for user confirmation on key decisions  
**Complexity**: Medium (new library integration, camera APIs)  
**Risk**: Low (self-contained, graceful fallbacks)  
**Value**: High (major mobile UX improvement, desktop convenience)

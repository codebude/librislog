# Plan: ISBN Barcode Scanner for Import Dialog

## Overview

Add a barcode scanner button to the Import tab that uses the device camera to scan ISBN barcodes (EAN-13, EAN-8, UPC-A, etc.) and automatically trigger an ISBN-based import search. This feature must work on both desktop and mobile browsers without requiring a native app.

**Goal**: Allow users to quickly import books by scanning the barcode on the back cover, eliminating manual ISBN entry and improving mobile UX.

---

## Current State Analysis

### Backend
- **Import endpoints**:
  - `GET /api/import/search/stream` — Server-Sent Events (SSE) stream for progress tracking
  - `POST /api/import` — Import a candidate into local database
  - Both support `type="isbn"` query parameter for ISBN searches
- **Search service**: `app.services.book_import.search_with_progress()` handles Open Library + Google Books
- **No backend changes needed** for barcode scanning (frontend-only feature)

### Frontend
- **ImportSearch.svelte**: 
  - Currently has text input + type selector (title/isbn) + search button
  - Already supports ISBN search mode (`searchType = 'isbn'`)
  - Search is triggered by `search()` function which calls `api.import.searchStream()`
- **Tech stack**: 
  - SvelteKit 2.x (Svelte 5 runes)
  - Tailwind CSS v4 + DaisyUI v5
  - No existing camera/media APIs in use
- **Browser compatibility**: Modern browsers (Chrome, Safari, Firefox, Edge) via SvelteKit SPA mode

### User Flow (Current)
1. User opens "Add Book" modal → clicks "Search & Import" tab
2. User manually types ISBN in text input
3. User changes dropdown to "ISBN" mode
4. User clicks "Search" button
5. Results populate, user clicks "Add"

### User Flow (Proposed with Scanner)
1. User opens "Add Book" modal → clicks "Search & Import" tab
2. User clicks new "📷 Scan Barcode" button
3. Camera view opens in a modal/overlay
4. Camera auto-detects barcode → scanner closes
5. ISBN is auto-populated in search input → search automatically triggers in ISBN mode
6. Results populate, user clicks "Add"

---

## Problem Statement

**Pain points**:
1. **Manual ISBN entry is slow and error-prone** (13-digit codes are hard to type accurately on mobile)
2. **Mobile keyboards take up screen space**, making the import UI cramped
3. **No quick way to bulk-scan** multiple books (though out of scope for initial version)
4. **Desktop users with webcams can't leverage them** for book cataloging

**User expectations**:
- Single-click scanner activation
- Fast barcode detection (< 2 seconds on good lighting)
- Clear permission requests (camera access)
- Graceful fallback if camera unavailable
- Works on phone, tablet, and desktop

---

## Requirements

### Functional
1. ✅ **Scanner button** in ImportSearch component, next to search input
2. ✅ **Camera modal/overlay** opens when button is clicked
3. ✅ **Barcode detection** for ISBN formats (EAN-13, EAN-8, UPC-A, UPC-E)
4. ✅ **Auto-trigger search** when barcode is detected (close scanner + run ISBN search)
5. ✅ **Camera permissions** properly requested (browser native prompt)
6. ✅ **Mobile support** (rear camera preferred on phones)
7. ✅ **Desktop support** (any available webcam)
8. ✅ **Close button** to cancel scanning
9. ✅ **Error handling** for:
   - Camera permission denied
   - No camera available
   - Scanner library load failure
   - Barcode detection errors (poor lighting, damaged barcode)

### Non-Functional
- **Performance**: Barcode detection in < 2 seconds (good lighting)
- **UX**: Smooth modal animation, clear loading states, no layout shift
- **Accessibility**: Keyboard navigation (Escape to close), ARIA labels
- **Browser support**: Chrome 90+, Safari 14+, Firefox 88+, Edge 90+ (MediaStream API support)
- **Bundle size**: Library should be < 100KB gzipped (loaded lazily if possible)

### Out of Scope (Future Enhancements)
- Bulk scanning (scan multiple books in sequence)
- Manual barcode entry during scan (e.g., for damaged barcodes)
- QR code support (for book URLs)
- Scan history (list of recently scanned ISBNs)
- Scan-to-search from main book list (outside import modal)
- Offline barcode detection (requires IndexedDB + service worker)

---

## Technology Selection

### Library Evaluation

After researching JavaScript barcode scanning libraries, the candidates are:

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| **html5-qrcode** | ✅ 11k+ stars, Apache-2.0<br>✅ Built-in UI components<br>✅ ISBN barcode formats supported (EAN-13, UPC, CODE-128)<br>✅ Mobile + desktop support<br>✅ Active maintenance (2024)<br>✅ Good TypeScript support<br>✅ ~45KB gzipped | ⚠️ Heavier than pure barcode libs (includes QR) | ✅ **RECOMMENDED** |
| **quagga2** | ✅ 18k+ stars, MIT<br>✅ Specialized for barcodes (lighter)<br>✅ Good EAN/UPC detection<br>✅ ~35KB gzipped | ⚠️ Steeper learning curve (no built-in UI)<br>⚠️ More manual camera setup<br>⚠️ Requires custom UI building | ⚠️ Alternative if size is critical |
| **@zxing/browser** | ✅ Part of ZXing ecosystem (Java port)<br>✅ Very accurate<br>✅ ~50KB gzipped | ⚠️ Less documented<br>⚠️ Manual camera handling<br>⚠️ More verbose API | ❌ More complex setup |

**Decision**: **Use `html5-qrcode`** 
- **Rationale**:
  - Well-documented, active maintenance
  - Built-in camera UI (torch button, camera selector)
  - Good mobile UX (aspect ratio, responsive)
  - Easy integration (few lines of code)
  - TypeScript definitions included
  - Proven in production (used by TiddlyWiki, Frappe, NocoBase)
  - Bundle size acceptable (45KB gzipped, lazy-loaded)

**Reference docs**: Use Context7 `/mebjas/html5-qrcode` for up-to-date API documentation during implementation.

---

## Implementation Plan

### Phase 1: Install Library and Create Scanner Component

#### Step 1.1: Add Dependency

**File**: `frontend/package.json`

```bash
cd frontend
npm install html5-qrcode
```

**Verify**: Check `package.json` shows `"html5-qrcode": "^2.x.x"` (latest stable)

#### Step 1.2: Create BarcodeScanner Component

**New file**: `frontend/src/lib/components/BarcodeScanner.svelte`

**Purpose**: Encapsulate barcode scanning logic in a reusable component.

**Props**:
- `open` (bindable boolean) — Controls modal visibility
- `onDetected` (callback) — Called with ISBN string when barcode is scanned

**Lifecycle**:
1. When `open` becomes `true` → initialize `Html5Qrcode`, request camera, start scanning
2. When barcode detected → call `onDetected(isbn)`, stop scanner, close modal
3. When `open` becomes `false` → stop scanner, release camera
4. On component destroy → cleanup (stop scanner if running)

**Configuration**:
```typescript
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode';

const scannerConfig = {
    fps: 10, // 10 frames per second (balance speed vs. CPU)
    qrbox: { width: 300, height: 150 }, // Wide rectangular region (barcodes are horizontal)
    aspectRatio: 1.777778, // 16:9 viewfinder
    formatsToSupport: [
        Html5QrcodeSupportedFormats.EAN_13,  // ISBN-13 (primary)
        Html5QrcodeSupportedFormats.EAN_8,   // ISBN-8 (short form)
        Html5QrcodeSupportedFormats.UPC_A,   // UPC-A (US books)
        Html5QrcodeSupportedFormats.UPC_E,   // UPC-E (compact)
        Html5QrcodeSupportedFormats.CODE_128 // Alternate format
    ],
    showTorchButtonIfSupported: true, // Flashlight on mobile
    showZoomSliderIfSupported: false, // Disable zoom (not needed)
    rememberLastUsedCamera: true,     // Use rear camera on mobile
    useBarCodeDetectorIfSupported: true // Use native browser API if available (faster)
};
```

**Why these formats**:
- **EAN-13**: Standard ISBN-13 format (978 prefix for books)
- **EAN-8**: Short ISBNs (rare but valid)
- **UPC-A/UPC-E**: US book barcodes (10-digit ISBNs)
- **CODE-128**: Fallback for older book barcodes

**Camera selection strategy**:
- **Mobile**: Prefer rear camera (environment-facing) via `{ facingMode: "environment" }`
- **Desktop**: Use first available camera (usually built-in webcam)
- **Fallback**: If rear camera fails on mobile, try front camera

**Implementation structure**:
```svelte
<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode';
    import { toasts } from '$lib/toasts';

    let {
        open = $bindable(false),
        onDetected
    }: {
        open?: boolean;
        onDetected?: (isbn: string) => void;
    } = $props();

    let scanner: Html5Qrcode | null = null;
    let scanning = $state(false);
    let error = $state<string | null>(null);
    let containerId = 'barcode-scanner-' + Math.random().toString(36).slice(2);

    // Effect: start/stop scanner when open changes
    $effect(() => {
        if (open && !scanning) {
            startScanner();
        } else if (!open && scanning) {
            stopScanner();
        }
    });

    async function startScanner() {
        // ... initialize Html5Qrcode, request camera, start scanning
    }

    async function stopScanner() {
        // ... stop scanner, release camera
    }

    function handleScanSuccess(decodedText: string, result: any) {
        // ... validate ISBN, call onDetected, close modal
    }

    function handleScanFailure(errorMessage: string) {
        // ... ignore (called every frame when no barcode found)
    }

    function close() {
        open = false;
    }

    onDestroy(() => {
        if (scanner && scanning) {
            stopScanner().catch(console.error);
        }
    });
</script>

{#if open}
    <div class="modal modal-open">
        <div class="modal-box w-full max-w-md">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold">Scan Barcode</h3>
                <button class="btn btn-ghost btn-sm btn-circle" onclick={close}>✕</button>
            </div>

            {#if error}
                <div class="alert alert-error mb-4">
                    <span>{error}</span>
                </div>
            {/if}

            <!-- Scanner renders here -->
            <div id={containerId} class="rounded-lg overflow-hidden"></div>

            <p class="text-sm text-base-content/60 mt-4 text-center">
                Position the barcode within the frame
            </p>
        </div>
        <div class="modal-backdrop" onclick={close}></div>
    </div>
{/if}
```

**Error handling**:
- **Permission denied**: Show alert "Camera access denied. Please allow camera access in browser settings."
- **No camera**: Show alert "No camera found. Please connect a camera or enter ISBN manually."
- **Scanner initialization fails**: Show alert with generic error message
- **All errors**: Toast notification + close modal

**Performance considerations**:
- **Lazy load**: Import `html5-qrcode` dynamically if scanner is never opened (future optimization)
- **Cleanup**: Always call `scanner.stop()` before destroying component to release camera
- **FPS throttling**: Use `fps: 10` to balance detection speed vs. CPU usage

---

### Phase 2: Integrate Scanner into ImportSearch Component

#### Step 2.1: Add Scanner Button

**File**: `frontend/src/lib/components/ImportSearch.svelte`

**Changes**:

1. **Import BarcodeScanner**:
```typescript
import BarcodeScanner from './BarcodeScanner.svelte';
```

2. **Add scanner state**:
```typescript
let scannerOpen = $state(false);
```

3. **Add scanner button** (after the search button):
```svelte
<div class="flex gap-2">
    <input
        type="text"
        class="input input-bordered input-sm flex-1"
        placeholder={searchType === 'isbn' ? 'Enter ISBN…' : 'Search by title or author…'}
        bind:value={query}
        onkeydown={(e) => e.key === 'Enter' && search()}
    />
    <select class="select select-bordered select-sm" bind:value={searchType}>
        <option value="title">Title</option>
        <option value="isbn">ISBN</option>
    </select>
    <!-- NEW: Scanner button -->
    <button 
        class="btn btn-outline btn-sm" 
        onclick={() => { scannerOpen = true; }}
        title="Scan barcode"
        aria-label="Scan barcode with camera"
    >
        📷
    </button>
    <button class="btn btn-primary btn-sm" onclick={search} disabled={searching}>
        {searching ? '…' : 'Search'}
    </button>
</div>
```

**Design notes**:
- **Icon**: Camera emoji (📷) — recognizable, no icon library needed
- **Button style**: `btn-outline` (secondary action, not primary)
- **Size**: `btn-sm` (matches search button)
- **Accessibility**: `aria-label` for screen readers
- **Tooltip**: `title` attribute explains button function

**Alternative icons** (if emoji is not preferred):
- Text: "Scan" or "📷 Scan"
- SVG icon (requires adding icon library or inline SVG)
- DaisyUI icon class (if available in v5)

4. **Add scanner modal** (at the end of the component):
```svelte
<BarcodeScanner 
    bind:open={scannerOpen}
    onDetected={(isbn) => handleBarcodeDetected(isbn)}
/>
```

5. **Add handler function**:
```typescript
function handleBarcodeDetected(isbn: string) {
    // 1. Set search type to ISBN
    searchType = 'isbn';
    
    // 2. Populate query with detected ISBN
    query = isbn.trim();
    
    // 3. Auto-trigger search
    search();
    
    // 4. Show success toast
    toasts.add(`Scanned ISBN: ${isbn}`, 'success');
}
```

**UX flow**:
1. User clicks "📷" button
2. Scanner modal opens with camera view
3. User positions book barcode in frame
4. Barcode detected → modal closes
5. Search input populates with ISBN, search runs automatically
6. Results appear (user can immediately click "Add")

**Why auto-search**:
- **Reduces friction**: User doesn't need to click "Search" after scanning
- **Faster workflow**: Scan → results in ~3 seconds
- **Expected behavior**: Most barcode scanner apps auto-execute action after scan

---

### Phase 3: Handle Edge Cases and Errors

#### Edge Case 1: Camera Permission Denied

**Scenario**: User clicks scanner button → browser prompts for camera → user clicks "Block"

**Handling**:
- `Html5Qrcode.start()` throws error
- Catch error, check if it's permission-related (string match: "permission", "denied", "NotAllowedError")
- Show user-friendly error message:
  ```
  Camera access denied. To scan barcodes, please:
  1. Allow camera access in browser settings
  2. Reload the page
  Or enter ISBN manually.
  ```
- Provide link to browser help docs (if feasible)

**UX improvement**: 
- Don't show scanner button if camera API not available (`navigator.mediaDevices` check)
- Or disable button with tooltip "Camera not available"

#### Edge Case 2: No Camera Available

**Scenario**: Desktop user without webcam, or device without camera

**Handling**:
- Check `navigator.mediaDevices.enumerateDevices()` before opening scanner
- If no video input devices found → show toast "No camera found" + don't open modal
- Or show error inside modal (depends on when check happens)

**Implementation**:
```typescript
async function openScanner() {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const hasCamera = devices.some(device => device.kind === 'videoinput');
        if (!hasCamera) {
            toasts.add('No camera found. Please enter ISBN manually.', 'error');
            return;
        }
        scannerOpen = true;
    } catch (e) {
        toasts.add('Camera not available', 'error');
    }
}
```

**Alternative**: Let `Html5Qrcode` handle this (it will throw error if no camera) — simpler but less proactive.

#### Edge Case 3: Invalid Barcode Detected

**Scenario**: Scanner detects a barcode, but it's not an ISBN (e.g., product barcode, QR code)

**Handling**:
- **Validate ISBN format** in `handleBarcodeDetected()`:
  - ISBN-13: 13 digits starting with 978 or 979
  - ISBN-10: 10 digits (convert to 13 for search)
  - EAN-13: 13 digits (may be valid for books)
- If invalid → show toast "Invalid ISBN scanned. Please try again or enter manually."
- **Do not auto-search** with invalid ISBN

**Validation logic**:
```typescript
function isValidIsbn(code: string): boolean {
    const cleaned = code.replace(/[^0-9X]/gi, ''); // Remove dashes, spaces
    
    // ISBN-13 or EAN-13 (13 digits)
    if (cleaned.length === 13) {
        return /^(978|979)\d{10}$/.test(cleaned) || /^\d{13}$/.test(cleaned);
    }
    
    // ISBN-10 (10 digits, may end with X)
    if (cleaned.length === 10) {
        return /^\d{9}[\dX]$/i.test(cleaned);
    }
    
    return false;
}
```

**ISBN-10 to ISBN-13 conversion** (if needed):
- Prepend "978"
- Recalculate check digit
- This ensures consistent search format

#### Edge Case 4: Poor Lighting / Damaged Barcode

**Scenario**: Camera open, but barcode is not detected (too dark, barcode damaged, too far)

**Handling**:
- **Torch button**: Enabled by default (`showTorchButtonIfSupported: true`) — user can turn on flashlight on mobile
- **User feedback**: No automatic feedback (scanner keeps running)
- **Manual fallback**: User can close scanner and enter ISBN manually

**UX hint**: Add text below scanner: "Tip: Use good lighting and hold barcode steady"

#### Edge Case 5: Scanner Stuck Open (Component Unmount)

**Scenario**: User opens scanner → navigates away or closes modal before scanner stops

**Handling**:
- `onDestroy()` lifecycle hook stops scanner and releases camera
- Also stop scanner when `open` prop becomes `false` (via `$effect`)

```typescript
onDestroy(() => {
    if (scanner && scanning) {
        scanner.stop().catch(err => {
            console.error('Failed to stop scanner on destroy:', err);
        });
    }
});
```

#### Edge Case 6: Multiple Barcodes in Frame

**Scenario**: Book has multiple barcodes (ISBN + price barcode)

**Handling**:
- `html5-qrcode` returns first detected barcode
- If wrong barcode detected → user can close scanner and try again, or enter manually
- **Future enhancement**: Show detected barcode in preview, let user confirm before searching

#### Edge Case 7: Browser Not Supported

**Scenario**: User on old browser without `MediaStream` API (IE11, old Safari)

**Handling**:
- Check `navigator.mediaDevices` availability
- If not available → hide scanner button OR disable with tooltip
- Graceful degradation: manual ISBN entry still works

```typescript
const isCameraSupported = $derived(
    typeof navigator !== 'undefined' && 
    navigator.mediaDevices && 
    navigator.mediaDevices.getUserMedia
);
```

```svelte
{#if isCameraSupported}
    <button class="btn btn-outline btn-sm" onclick={openScanner}>📷</button>
{/if}
```

---

### Phase 4: Mobile Optimizations

#### Mobile-Specific Considerations

1. **Rear Camera Preference**:
   - Use `facingMode: "environment"` constraint
   - Falls back to front camera if rear not available

```typescript
const cameraConfig = {
    facingMode: { ideal: "environment" } // Prefer rear camera
};
await scanner.start(cameraConfig, scannerConfig, onSuccess, onFailure);
```

2. **Viewport Meta Tag** (should already be present):
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
```

3. **Fullscreen Modal on Mobile**:
   - Make scanner modal larger on small screens
   - Consider full-screen overlay (no margin) on phones

```svelte
<div class="modal-box w-full max-w-md md:max-w-lg h-auto md:h-auto sm:h-[90vh]">
```

4. **Touch Optimization**:
   - Larger close button (easier to tap)
   - Clear visual feedback on button press

5. **Performance**:
   - Lower FPS on older mobile devices if needed (`fps: 5` for budget phones)
   - Could detect device performance and adjust (future optimization)

#### Mobile Testing Checklist

- ✅ Camera permission request appears correctly
- ✅ Rear camera is selected by default
- ✅ Torch button appears and works (if device supports)
- ✅ Scanner fills modal viewport (no horizontal scroll)
- ✅ Close button is easily tappable (44×44 px minimum)
- ✅ Barcode detection works in various lighting
- ✅ Scanner stops when modal closes (camera indicator turns off)
- ✅ Scanning from distance (~10-20 cm) works
- ✅ Works in both portrait and landscape mode

---

### Phase 5: Desktop Optimizations

#### Desktop-Specific Considerations

1. **Webcam Selection**:
   - If multiple cameras (built-in + external), let user choose
   - `html5-qrcode` provides camera selector dropdown (built-in UI)

2. **Keyboard Shortcuts**:
   - **Escape key** → Close scanner modal
   - Already handled by modal backdrop (DaisyUI default)

3. **Larger Scanner Region**:
   - Desktop has more screen space → use larger `qrbox`
   - Responsive sizing:

```typescript
const isDesktop = window.innerWidth >= 768;
const qrbox = isDesktop 
    ? { width: 400, height: 200 }  // Larger on desktop
    : { width: 300, height: 150 }; // Smaller on mobile
```

4. **Mouse Hover Feedback**:
   - Scanner button hover effect (DaisyUI handles this)

#### Desktop Testing Checklist

- ✅ Webcam permission request appears correctly
- ✅ Camera selector dropdown works (if multiple cameras)
- ✅ Scanner modal is appropriately sized (not too small)
- ✅ Close button works via click and Escape key
- ✅ Barcode detection works with built-in webcam
- ✅ No performance issues (smooth video feed at 10 FPS)
- ✅ Works in Chrome, Safari, Firefox, Edge

---

## Testing Plan

### Backend Tests

**No backend changes** → no new backend tests needed.

**Existing tests** should continue to pass (no regressions):
- `test_import.py` — search and import endpoints unchanged

### Frontend Tests

#### Manual Testing Checklist

##### Basic Functionality
1. **✅ Scanner button appears** in Import tab
2. **✅ Scanner button click opens modal** with camera view
3. **✅ Camera permission request** appears on first use
4. **✅ Scanner starts** after permission granted (camera indicator on)
5. **✅ Barcode detection works** (scan a book barcode)
6. **✅ ISBN populates search input** after detection
7. **✅ Search auto-triggers** in ISBN mode after scan
8. **✅ Results appear** correctly (same as manual ISBN search)
9. **✅ Scanner modal closes** after successful scan
10. **✅ Close button works** (via ✕ button and backdrop click)

##### Error Handling
11. **✅ Camera permission denied** → shows user-friendly error
12. **✅ No camera available** → shows error or hides button
13. **✅ Invalid barcode scanned** → shows error, doesn't search
14. **✅ Scanner fails to initialize** → shows generic error
15. **✅ Scanner stuck open** → cleanup on navigation/unmount

##### Mobile-Specific
16. **✅ Rear camera is used** by default on mobile
17. **✅ Torch button appears** on mobile (if supported)
18. **✅ Torch button works** (enables flashlight)
19. **✅ Scanner works in portrait** mode
20. **✅ Scanner works in landscape** mode
21. **✅ Modal is responsive** (no layout breaks on small screens)
22. **✅ Close button is easily tappable** (large enough)

##### Desktop-Specific
23. **✅ Webcam is selected** correctly
24. **✅ Camera selector dropdown** works (if multiple cameras)
25. **✅ Escape key closes** modal
26. **✅ Scanner region is appropriately sized** (not too small)

##### Performance
27. **✅ Barcode detected in < 3 seconds** (good lighting)
28. **✅ No lag or frame drops** during scanning
29. **✅ Camera releases** after modal closes (indicator turns off)

##### Accessibility
30. **✅ Keyboard navigation** works (Tab to buttons, Enter to activate)
31. **✅ Screen reader** announces button purpose (aria-label)
32. **✅ Focus management** (focus returns to button after modal closes)

#### Devices to Test

**Mobile**:
- iPhone (Safari)
- Android phone (Chrome)

**Desktop**:
- macOS (Chrome, Safari)
- Windows (Chrome, Edge)
- Linux (Firefox)

#### Test ISBNs

Use real books for testing, or these test barcodes:
- **ISBN-13**: 9780441013593 (Dune by Frank Herbert)
- **ISBN-10**: 0441013597 (same book, old format)
- **EAN-13**: 9780545010221 (Harry Potter)
- **UPC-A**: 123456789012 (not an ISBN — should fail validation)

#### Browser DevTools Testing

1. **Throttle network** (ensure scanner works on slow connections)
2. **Throttle CPU** (test FPS performance on low-end devices)
3. **Simulate camera** (use DevTools sensor emulation for testing without camera)
4. **Check console** for errors during scanner lifecycle

#### Integration Tests (Future — Playwright)

**File**: `frontend/tests/barcode-scanner.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('Barcode Scanner', () => {
    test.beforeEach(async ({ page, context }) => {
        // Grant camera permissions
        await context.grantPermissions(['camera']);
        await page.goto('/');
    });

    test('should open scanner modal when button clicked', async ({ page }) => {
        await page.click('text=+ Add Book');
        await page.click('text=Search & Import');
        await page.click('button[title="Scan barcode"]');
        
        // Scanner modal should appear
        await expect(page.locator('text=Scan Barcode')).toBeVisible();
        // Video element should be present (camera started)
        await expect(page.locator('video')).toBeVisible();
    });

    test('should close scanner when close button clicked', async ({ page }) => {
        await page.click('text=+ Add Book');
        await page.click('text=Search & Import');
        await page.click('button[title="Scan barcode"]');
        
        // Close scanner
        await page.click('.modal-box .btn-circle');
        
        // Modal should disappear
        await expect(page.locator('text=Scan Barcode')).not.toBeVisible();
    });

    // Note: Actual barcode scanning is hard to test in Playwright
    // (requires injecting test frames into video stream or mocking Html5Qrcode)
    // Consider manual testing or end-to-end tests with real camera hardware
});
```

**Limitation**: Playwright can't easily simulate barcode scanning (requires video stream injection). Recommend **manual testing** for barcode detection accuracy.

---

## Implementation Steps

### Step 1: Install Library
**Estimated time**: 5 minutes

```bash
cd frontend
npm install html5-qrcode
```

Verify installation: Check `package.json` and run `npm run dev` (no errors).

### Step 2: Create BarcodeScanner Component
**Estimated time**: 2 hours

**File**: `frontend/src/lib/components/BarcodeScanner.svelte`

1. Set up component structure (props, state, lifecycle hooks)
2. Implement `startScanner()` function (initialize `Html5Qrcode`, request camera)
3. Implement `stopScanner()` function (cleanup)
4. Implement `handleScanSuccess()` (validate ISBN, call callback)
5. Add error handling for all camera/scanner operations
6. Build modal UI (scanner container, close button, error display)
7. Test in isolation (hardcoded `open = true` in parent)

**Key implementation details**:
- Use `$effect` to watch `open` prop and start/stop scanner
- Use `onDestroy` for cleanup
- Generate unique `containerId` for scanner (avoid ID conflicts)
- Use `Html5QrcodeSupportedFormats` enum for format restriction
- Prefer `facingMode: "environment"` on mobile

### Step 3: Integrate into ImportSearch
**Estimated time**: 45 minutes

**File**: `frontend/src/lib/components/ImportSearch.svelte`

1. Import `BarcodeScanner` component
2. Add `scannerOpen` state variable
3. Add scanner button in search bar (after type selector)
4. Add `<BarcodeScanner>` component at end of template
5. Implement `handleBarcodeDetected()` function
6. Test scanner button click → modal opens → manual close works

### Step 4: Handle Edge Cases
**Estimated time**: 1 hour

1. Add camera availability check (hide button if no camera)
2. Implement ISBN validation in `handleBarcodeDetected()`
3. Add user-friendly error messages for common failures
4. Test permission denial flow
5. Test invalid barcode flow
6. Test no camera flow

### Step 5: Mobile & Desktop Optimization
**Estimated time**: 30 minutes

1. Add responsive `qrbox` sizing (larger on desktop)
2. Test rear camera preference on mobile
3. Test torch button on mobile
4. Verify keyboard shortcuts work (Escape to close)
5. Adjust modal sizing for mobile (full-height on small screens)

### Step 6: Manual Testing
**Estimated time**: 1.5 hours

Run through all 30+ test cases documented above:
- 10 basic functionality tests
- 5 error handling tests
- 7 mobile-specific tests
- 4 desktop-specific tests
- 3 performance tests
- 3 accessibility tests

Test on at least 2 devices (1 mobile, 1 desktop) across 2-3 browsers.

### Step 7: Documentation
**Estimated time**: 20 minutes

1. Add inline code comments explaining scanner config choices
2. Update README.md with note about camera permissions
3. Add JSDoc comments to `BarcodeScanner` component props
4. Document known limitations (e.g., damaged barcodes, poor lighting)

---

## Success Criteria

1. ✅ Scanner button appears in Import tab
2. ✅ Scanner modal opens with camera view
3. ✅ Barcode is detected and populates search input
4. ✅ Search auto-triggers in ISBN mode after scan
5. ✅ Scanner works on mobile (rear camera, torch button)
6. ✅ Scanner works on desktop (webcam, keyboard shortcuts)
7. ✅ Camera permissions are requested and handled gracefully
8. ✅ Error states are user-friendly (permission denied, no camera, invalid barcode)
9. ✅ Scanner stops and releases camera when modal closes
10. ✅ No performance issues (smooth video at 10 FPS)
11. ✅ Barcode detection completes in < 3 seconds (good lighting)
12. ✅ All manual tests pass on mobile and desktop

---

## Edge Cases Summary

| Scenario | Behavior | Status |
|----------|----------|--------|
| Camera permission denied | Show user-friendly error, suggest settings | ✅ Handled |
| No camera available | Show error or hide button | ✅ Handled |
| Invalid barcode scanned | Show error, don't auto-search | ✅ Handled |
| Poor lighting / damaged barcode | User can retry or use torch | ⚠️ User fallback |
| Multiple barcodes in frame | First detected is used | ⚠️ Known limitation |
| Scanner stuck open (unmount) | Cleanup in `onDestroy` | ✅ Handled |
| Browser not supported | Hide button or show error | ✅ Handled |
| Rear camera not available (mobile) | Fall back to front camera | ✅ Handled |
| User navigates away during scan | Scanner stops, camera released | ✅ Handled |
| Scanner modal opened twice | Second open ignored (scanner already running) | ✅ Handled |

---

## Performance Considerations

### Bundle Size Impact

**Before**: 
- Current frontend bundle: ~150KB gzipped (estimated from SvelteKit + DaisyUI)

**After**:
- `html5-qrcode` library: ~45KB gzipped
- New component code: ~3KB gzipped
- **Total impact**: +48KB (~32% increase)

**Optimization options** (future):
1. **Lazy load** scanner library (dynamic import when button clicked):
   ```typescript
   async function openScanner() {
       const { Html5Qrcode, Html5QrcodeSupportedFormats } = await import('html5-qrcode');
       // ... rest of scanner logic
   }
   ```
   - **Benefit**: Library only loaded if user clicks scanner button
   - **Trade-off**: Slight delay on first scan (~200ms)

2. **Tree-shake unused formats** (if library supports):
   - Only include EAN/UPC formats, exclude QR/Data Matrix
   - May require custom build (check library docs)

3. **Code splitting** at route level:
   - Scanner code only bundled with Import route
   - SvelteKit handles this automatically

**Decision**: **Accept initial bundle size increase** (45KB is reasonable for this feature). Implement lazy loading if user feedback indicates slow load times.

### Runtime Performance

**CPU usage**:
- 10 FPS video processing: ~10-20% CPU on modern devices
- Lower on devices with native `BarcodeDetector` API (use `useBarCodeDetectorIfSupported: true`)

**Memory usage**:
- Scanner holds video stream in memory: ~10-30 MB
- Released when scanner stops

**Battery impact**:
- Camera + processing: moderate battery drain
- Not significant for short scanning sessions (< 1 minute)

**Mitigation**:
- Stop scanner immediately after detection (don't leave camera running)
- Auto-stop after 60 seconds of no detection (future enhancement)

---

## Browser Compatibility

| Browser | Version | Status | Notes |
|---------|---------|--------|-------|
| Chrome | 90+ | ✅ Full support | Best performance, native BarcodeDetector |
| Safari | 14+ | ✅ Full support | iOS 14+ required for mobile |
| Firefox | 88+ | ✅ Full support | Slightly slower detection |
| Edge | 90+ | ✅ Full support | Chromium-based, same as Chrome |
| Samsung Internet | 14+ | ✅ Full support | Android only |
| Opera | 76+ | ✅ Full support | Chromium-based |
| IE11 | — | ❌ Not supported | No MediaStream API |

**Progressive enhancement**:
- Scanner button **hidden** if `navigator.mediaDevices` not available
- Manual ISBN entry still works on all browsers

**Mobile browsers**:
- **iOS Safari**: Requires iOS 14+ (MediaStream API)
- **Chrome Mobile**: Full support on Android 7+
- **Firefox Mobile**: Full support on Android 7+

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Camera permission always denied by users | Low | Medium | Provide clear value proposition before asking for permission; manual entry still works |
| Barcode detection too slow (> 5 seconds) | Low | Medium | Use `useBarCodeDetectorIfSupported: true` for native API; allow manual fallback |
| Poor lighting causes detection failure | Medium | Low | Enable torch button on mobile; show tip about lighting |
| Bundle size too large (slow load) | Low | Medium | Lazy load scanner library; only load on first button click |
| Library maintenance stops | Low | High | `html5-qrcode` is actively maintained (2024), 11k+ stars; can switch to quagga2 if needed |
| Incompatible barcodes (damaged, non-ISBN) | Medium | Low | Validate ISBN before searching; show error for invalid codes |
| User confusion about scanner UX | Low | Low | Clear button label, tooltip, in-modal instructions |

---

## Future Enhancements

1. **Bulk scanning mode**: Scan multiple books in sequence without closing modal
2. **Scan history**: Show list of recently scanned ISBNs (persisted in localStorage)
3. **Manual barcode entry**: Fallback input field inside scanner modal for damaged barcodes
4. **QR code support**: Scan QR codes linking to book pages (Open Library, Goodreads)
5. **Offline detection**: Use IndexedDB to cache scanner library for offline use
6. **Custom barcode overlays**: Show bounding box around detected barcode for visual feedback
7. **Auto-stop timeout**: Close scanner after 60 seconds of inactivity to save battery
8. **Zoom control**: Manual zoom slider for desktop webcams (currently only on mobile)
9. **Sound/haptic feedback**: Beep or vibration on successful scan (mobile)
10. **Scanner settings**: Allow user to configure FPS, qrbox size, camera preference
11. **Analytics**: Track scan success rate, average scan time (privacy-respecting)

---

## Dependencies

**New dependency**:
- **`html5-qrcode`**: `^2.x` (latest stable)
  - License: Apache-2.0 (permissive, commercial-friendly)
  - Bundle size: ~45KB gzipped
  - TypeScript support: Built-in `.d.ts` files

**Existing dependencies** (no changes):
- Svelte 5, SvelteKit 2.x
- DaisyUI v5 (modal component, button styles)
- Tailwind CSS v4 (utility classes)

**Browser APIs used**:
- `navigator.mediaDevices.getUserMedia()` (camera access)
- `navigator.mediaDevices.enumerateDevices()` (camera detection)
- `BarcodeDetector` API (optional, if available — native detection)

---

## Rollback Plan

If critical issues arise after deployment:

1. **Quick disable** (feature flag approach):
   - Wrap scanner button in `{#if false}` to hide it
   - Deploy hotfix (< 5 minutes)
   - Investigate issue offline

2. **Full rollback** (remove feature):
   - Remove `BarcodeScanner.svelte` component
   - Remove scanner button from `ImportSearch.svelte`
   - Uninstall `html5-qrcode` from `package.json`
   - Rebuild and deploy
   - **Rollback time**: < 15 minutes

**Rollback complexity**: Low — feature is self-contained (1 new component, 1 button, 1 library)

---

## Implementation Estimate

| Step | Description | Time |
|------|-------------|------|
| 1 | Install library | 5 min |
| 2 | Create BarcodeScanner component | 2 hours |
| 3 | Integrate into ImportSearch | 45 min |
| 4 | Handle edge cases | 1 hour |
| 5 | Mobile & desktop optimization | 30 min |
| 6 | Manual testing | 1.5 hours |
| 7 | Documentation | 20 min |
| **Total** | | **~6.5 hours** |

**Buffer for unknowns**: +1.5 hours (scanner API quirks, device-specific issues)

**Realistic estimate**: **8 hours** (1 full day of focused development)

---

## Documentation Updates

After implementation:

1. **README.md**: Add note about camera permissions in "Features" section
2. **Component JSDoc**: Document `BarcodeScanner` props and behavior
3. **`.plan/05-milestones.md`**: Add "ISBN Barcode Scanner" milestone (if tracking features)
4. **Inline comments**: Explain scanner config choices, ISBN validation logic

---

## Conclusion

This implementation provides a **fast, user-friendly barcode scanning feature** using the well-maintained `html5-qrcode` library. The approach prioritizes:

- **Ease of use**: Single-click scanner, auto-search on detection
- **Broad compatibility**: Works on mobile and desktop, iOS and Android
- **Robust error handling**: Graceful fallbacks for common failure modes
- **Performance**: Native BarcodeDetector API where available, lazy loading potential
- **Maintainability**: Self-contained component, clear separation of concerns

The feature integrates seamlessly with the existing import workflow and requires **no backend changes**. Testing can be completed manually in ~1.5 hours, with future Playwright tests for regression coverage.

**Estimated delivery**: 1 day of focused development + testing.

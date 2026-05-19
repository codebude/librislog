# Chart Library Refactor Plan

## Overview

Replace self-built SVG line charts in `frontend/src/routes/statistics/+page.svelte` with a professional charting library to fix hover tooltips, axis alignment, and visual quality issues.

**Current Problems:**
- No interactive hover tooltips (only SVG `<title>` elements)
- X-axis labels are manually positioned and don't align properly with data points
- Custom SVG path calculation (`buildLine()` function) is error-prone
- Poor visual consistency with modern charting UX expectations

**Target Improvements:**
- Interactive hover tooltips showing exact values
- Proper axis alignment and gridlines
- Smooth animations and professional appearance
- Maintained DaisyUI theme integration
- Mobile-responsive charts

---

## 1. Library Selection

### Recommended: **Chart.js v4 + `svelte-chartjs`**

**Why Chart.js:**
- ✅ **License:** MIT (100% free, no commercial restrictions)
- ✅ **Svelte 5 Compatibility:** `svelte-chartjs` v4 supports Svelte 5 runes
- ✅ **Production-Ready:** Used by millions (GitHub: 65k+ stars, npm: 5M+ weekly downloads)
- ✅ **Line Charts:** Excellent support with hover tooltips, animations, responsive design
- ✅ **Tailwind/DaisyUI Compatible:** CSS-independent, colors/styles fully customizable via JS config
- ✅ **TypeScript Support:** First-class TypeScript definitions
- ✅ **Bundle Size:** ~180KB minified (acceptable for this use case)
- ✅ **No Build Config Changes:** Works out-of-the-box with Vite/SvelteKit

**Alternatives Considered:**

| Library | License | Svelte 5 Support | Verdict |
|---------|---------|------------------|---------|
| **LayerChart** | MIT | ✅ Yes (Svelte-native) | Good option but newer/less mature than Chart.js. Consider if you prefer Svelte-first architecture. |
| **Apache ECharts** | Apache 2.0 | ⚠️ Via wrapper | Heavier bundle (~900KB), overkill for line charts |
| **Recharts** | MIT | ❌ React-only | Not compatible |
| **uPlot** | MIT | ✅ Framework-agnostic | Low-level API, more manual setup required |

**Final Decision:** Chart.js via `svelte-chartjs` provides the best balance of maturity, ease of use, bundle size, and Svelte 5 compatibility.

---

## 2. Installation Steps

### 2.1 Install Dependencies

```bash
cd frontend
npm install chart.js svelte-chartjs
```

**Packages:**
- `chart.js` (v4.x): Core charting library
- `svelte-chartjs` (v4.x): Official Svelte wrapper with runes support

### 2.2 Verify Installation

After install, confirm these appear in `package.json`:

```json
"dependencies": {
  "chart.js": "^4.x.x",
  "svelte-chartjs": "^4.x.x"
}
```

**No additional config required** — Chart.js works with existing Vite/Tailwind setup.

---

## 3. Component Structure

### 3.1 Create Reusable Chart Component

**Location:** `frontend/src/lib/components/LineChart.svelte`

**Purpose:**
- Encapsulate Chart.js setup and configuration
- Accept props for data, labels, colors, title
- Handle responsive sizing and DaisyUI theme colors
- Provide consistent tooltip/axis formatting

**Interface (Props):**
```typescript
interface Props {
  labels: string[];           // X-axis labels (e.g., ["Jan 2024", "Feb 2024", ...])
  data: number[];            // Y-axis data points
  label: string;             // Dataset label (e.g., "Pages Read")
  color: string;             // DaisyUI color class name (e.g., "primary", "secondary")
  locale?: string;           // For number formatting (default: "en")
}
```

**Why a separate component:**
- Reduces code duplication across 3 charts
- Centralizes Chart.js config (theme colors, fonts, animations)
- Easier to maintain and test
- Allows future chart types (bar, area) without touching page logic

### 3.2 Integration in Statistics Page

Replace the three self-built chart sections (lines 288-343) with `<LineChart>` component instances:

```svelte
<LineChart
  labels={pagesReadPoints.map(p => p.label)}
  data={pagesReadPoints.map(p => p.value)}
  label={$_('statistics.pagesReadPerMonth')}
  color="primary"
  locale={appLocale}
/>
```

**Benefits:**
- Declarative, readable code
- No manual SVG path calculations
- Automatic tooltip/hover handling
- Responsive by default

---

## 4. Data Mapping Strategy

### 4.1 Existing Data Structures

The statistics page already transforms API responses into `Point[]` arrays:

```typescript
type Point = { label: string; value: number; };

// Current transformations (lines 100-112):
const pagesReadPoints = toPoints(stats.pages_read_per_month);   // MonthlyPages[]
const booksByMonthPoints = toPoints(stats.books_finished_per_month); // MonthlyBooks[]
const booksByYearPoints = toYearPoints(stats.books_finished_per_year); // YearlyBooks[]
```

**Source Types (from `types.ts`):**
```typescript
interface MonthlyPages { month: string; pages: number; }
interface MonthlyBooks { month: string; count: number; }
interface YearlyBooks { year: number; count: number; }
```

### 4.2 Mapping to Chart.js Format

**No changes needed to data transformation logic!** The existing `Point[]` arrays perfectly map to Chart.js:

```typescript
// Chart.js expects:
const chartData = {
  labels: string[],        // X-axis
  datasets: [{
    label: string,
    data: number[],        // Y-axis
    // styling options...
  }]
};

// From existing Points:
const labels = points.map(p => p.label);  // Already formatted via formatMonthLabel()
const data = points.map(p => p.value);
```

**Advantages:**
- Existing `formatMonthLabel()` logic (line 58) still works
- Existing `formatNumber()` logic (line 53) reusable in tooltips
- No changes to API response handling
- Keep `toPoints()` and `toYearPoints()` helper functions

### 4.3 Example Data Flow

```
API Response → MonthlyPages[] → toPoints() → Point[] → LineChart props
```

**Before (SVG):**
```typescript
Point[] → buildLine() → { path, circles } → <svg><path/><circle/></svg>
```

**After (Chart.js):**
```typescript
Point[] → { labels, data } → <LineChart/> → Chart.js renders canvas
```

---

## 5. DaisyUI Theme Integration

### 5.1 Color Mapping

DaisyUI provides semantic color tokens via CSS variables. Chart.js needs RGB/hex values.

**Strategy:** Use CSS variable lookup at runtime.

**Implementation in `LineChart.svelte`:**

```typescript
function getDaisyUIColor(colorName: string): string {
  // Map DaisyUI semantic names to CSS variable names
  const cssVarMap: Record<string, string> = {
    'primary': '--p',
    'secondary': '--s',
    'accent': '--a',
    'info': '--in',
    'success': '--su',
    'warning': '--wa',
    'error': '--er'
  };
  
  const varName = cssVarMap[colorName];
  if (!varName) return 'rgb(0, 0, 0)'; // fallback
  
  // Get computed value from document root
  const hsl = getComputedStyle(document.documentElement)
    .getPropertyValue(varName)
    .trim();
  
  // Convert HSL to RGB for Chart.js
  // DaisyUI uses HSL format: "259 94% 51%"
  return hslToRgb(hsl);
}
```

**Alternative (Simpler):** Use Tailwind's color classes with `oklch()` CSS function (requires Chart.js v4.4+):

```typescript
const color = colorName === 'primary' ? 'oklch(var(--p))' : /* ... */;
```

### 5.2 Font and Spacing

Match DaisyUI typography:

```typescript
const chartOptions = {
  plugins: {
    legend: { labels: { font: { family: 'inherit' } } },
    tooltip: { titleFont: { family: 'inherit' }, bodyFont: { family: 'inherit' } }
  },
  scales: {
    x: { ticks: { font: { family: 'inherit' } } },
    y: { ticks: { font: { family: 'inherit' } } }
  }
};
```

**DaisyUI uses system font stack:**
- Already inherited via `font-family: inherit`
- No custom fonts to configure

### 5.3 Dark Mode Support

Chart.js respects CSS variables, so dark mode works automatically if:
- Colors use DaisyUI CSS variables (see 5.1)
- Text colors use `color: currentColor` or CSS variables
- Grid lines use `rgba(128, 128, 128, 0.1)` (theme-neutral)

**DaisyUI dark mode switching:** Handled by `data-theme` attribute on `<html>`. Chart.js will pick up new variable values on re-render.

---

## 6. Code Removal Plan

### 6.1 Functions to Remove

**File:** `frontend/src/routes/statistics/+page.svelte`

| Function/Type | Lines | Safe to Remove | Reason |
|---------------|-------|----------------|--------|
| `buildLine()` | 114-139 | ✅ Yes | SVG path calculation replaced by Chart.js |
| `chartLabels()` | 149-153 | ✅ Yes | Chart.js handles label thinning automatically |
| `Segment` type | 9-13 | ❌ No | Used by bar charts (language/status/page distributions) |
| `Point` type | 15-18 | ⚠️ Maybe | Still useful as intermediate format; consider keeping |
| `toPoints()` | 100-105 | ⚠️ Keep | Still useful for data transformation |
| `toYearPoints()` | 107-112 | ⚠️ Keep | Still useful for data transformation |

**Recommendation:** Keep `Point` type and transformation functions. They provide clean abstraction between API types and chart data.

### 6.2 Template Markup to Remove

**Remove (lines 287-343):**

```svelte
<!-- OLD: Pages Read Per Month SVG Chart -->
<div class="card bg-base-100 border border-base-200 shadow-sm">
  <div class="card-body gap-4">
    <h2 class="card-title text-base">{$_('statistics.pagesReadPerMonth')}</h2>
    <svg viewBox="0 0 360 140" ...>
      <path d={pagesReadLine.path} ... />
      {#each pagesReadLine.circles as point}
        <circle ... />
      {/each}
    </svg>
    <div class="flex justify-between gap-2 text-xs ...">
      {#each chartLabels(pagesReadPoints) as label} ... {/each}
    </div>
  </div>
</div>

<!-- Repeat for booksByMonth and booksByYear -->
```

**Replace with:**

```svelte
<div class="card bg-base-100 border border-base-200 shadow-sm">
  <div class="card-body">
    <h2 class="card-title text-base">{$_('statistics.pagesReadPerMonth')}</h2>
    <LineChart
      labels={pagesReadPoints.map(p => p.label)}
      data={pagesReadPoints.map(p => p.value)}
      label={$_('statistics.pagesReadPerMonth')}
      color="primary"
      locale={appLocale}
    />
  </div>
</div>

<!-- Similar for booksByMonth (color="secondary") and booksByYear (color="accent") -->
```

### 6.3 Derived State to Remove

**Remove (lines 145-147):**
```typescript
const pagesReadLine = $derived(buildLine(pagesReadPoints));
const booksByMonthLine = $derived(buildLine(booksByMonthPoints));
const booksByYearLine = $derived(buildLine(booksByYearPoints));
```

**These become unnecessary** once `buildLine()` is removed.

---

## 7. Implementation Steps (Ordered)

### Phase 1: Setup (No Breaking Changes)

1. **Install dependencies** (see §2.1)
   ```bash
   npm install chart.js svelte-chartjs
   ```

2. **Create `LineChart.svelte` component** (see §3.1)
   - File: `frontend/src/lib/components/LineChart.svelte`
   - Implement props interface
   - Configure Chart.js with DaisyUI colors
   - Test with hardcoded data first

3. **Verify component works standalone**
   - Create test route: `frontend/src/routes/test-chart/+page.svelte`
   - Render `<LineChart>` with sample data
   - Check hover tooltips, responsive behavior
   - **DO NOT commit test route** (delete after verification)

### Phase 2: Integration (Breaking Changes)

4. **Add import to statistics page**
   ```svelte
   <script lang="ts">
     import LineChart from '$lib/components/LineChart.svelte';
     // existing imports...
   </script>
   ```

5. **Replace first chart (Pages Read Per Month)**
   - Comment out SVG markup (lines 288-304)
   - Add `<LineChart>` component
   - Test in browser (localhost)
   - Verify data displays correctly

6. **Replace second chart (Books Finished Per Month)**
   - Repeat step 5 for lines 307-323
   - Change `color="secondary"`

7. **Replace third chart (Books Finished Per Year)**
   - Repeat step 5 for lines 326-342
   - Change `color="accent"`

8. **Remove old code** (see §6)
   - Delete `buildLine()` function
   - Delete `chartLabels()` function
   - Delete derived `*Line` variables
   - Keep `Point` type and transformation functions

### Phase 3: Polish & Testing

9. **Adjust styling**
   - Ensure chart heights match old design (~160px rendered height)
   - Verify card padding looks good
   - Test responsive behavior on mobile

10. **Test edge cases**
    - Empty data arrays (no stats available)
    - Single data point
    - Large datasets (12+ months)
    - Very small/large Y-axis values

11. **Cross-browser testing**
    - Chrome/Edge (Chromium)
    - Firefox
    - Safari (if available)
    - Mobile browsers (responsive mode)

12. **Accessibility audit**
    - Check keyboard navigation (Tab to focus chart, arrow keys to navigate points)
    - Verify screen reader announces chart data
    - Ensure color contrast meets WCAG AA

---

## 8. Testing Approach

### 8.1 Manual Testing Checklist

**Statistics Page (`/statistics`):**

- [ ] **Load Performance:** Page loads without errors or console warnings
- [ ] **Data Display:** All three charts render with correct data
- [ ] **Hover Tooltips:** Hovering over data points shows formatted value + label
- [ ] **Responsive Design:** Charts resize smoothly on window resize
- [ ] **Mobile View:** Charts are readable on 375px viewport
- [ ] **Dark Mode:** Charts adapt correctly when switching DaisyUI theme
- [ ] **Locale Support:** Number formatting respects `$locale` setting
- [ ] **Empty State:** Charts handle empty data gracefully (show "No data" or empty canvas)

**Edge Cases:**

- [ ] Single data point: Renders as single dot (no line)
- [ ] Two data points: Renders as straight line
- [ ] 12+ data points: X-axis labels don't overlap
- [ ] Large Y values (10,000+ pages): Axis scales appropriately
- [ ] Zero values: Chart shows baseline at zero

### 8.2 Visual Regression Testing

**Before/After Screenshots:**

1. Take screenshots of current SVG charts (all 3)
2. Implement new Chart.js version
3. Take screenshots of new charts
4. Compare side-by-side:
   - Are data points in same positions?
   - Are colors correct (primary/secondary/accent)?
   - Is overall layout preserved?

**Tool suggestion:** Use browser DevTools screenshot feature or Playwright for automation.

### 8.3 Automated Testing (Optional, Future)

**Unit Tests (Vitest):**
- Test `LineChart.svelte` with sample data
- Verify props are passed correctly to Chart.js
- Mock Chart.js canvas rendering

**Integration Tests (Playwright/Cypress):**
- Navigate to `/statistics`
- Assert chart canvas elements exist
- Simulate hover and check tooltip visibility

**Out of scope for initial implementation** — manual testing is sufficient for this refactor.

---

## 9. Rollback Plan

### If Chart.js Integration Fails:

**Scenario 1: Build/Runtime Errors**
- Uninstall packages: `npm uninstall chart.js svelte-chartjs`
- Revert `+page.svelte` changes via Git: `git checkout -- frontend/src/routes/statistics/+page.svelte`
- Delete `LineChart.svelte` component
- Verify old SVG charts still work

**Scenario 2: Visual Issues (But Functional)**
- Keep Chart.js installed
- Revert `+page.svelte` to old SVG markup temporarily
- Debug `LineChart.svelte` styling in isolation
- Re-integrate once fixed

**Scenario 3: Performance Regression**
- Check Chart.js bundle size impact: `npm run build` → inspect `frontend/build` size
- If > 200KB increase, consider lazy loading: `const LineChart = await import('$lib/components/LineChart.svelte')`

---

## 10. Post-Implementation Tasks

### 10.1 Documentation Updates

**Update (if exists):**
- `frontend/README.md`: Mention Chart.js dependency
- Project docs: Note chart library choice for future devs

### 10.2 Dependency Maintenance

**Add to dependency review process:**
- Monitor Chart.js releases: https://github.com/chartjs/Chart.js/releases
- Check `svelte-chartjs` compatibility with future Svelte versions

### 10.3 Future Enhancements (Out of Scope)

**Potential improvements (do NOT implement now):**
- Export charts as PNG/SVG (Chart.js plugin: `chartjs-plugin-download`)
- Animate chart transitions (Chart.js has built-in animations)
- Add zoom/pan for large datasets (plugin: `chartjs-plugin-zoom`)
- Show data table below chart for accessibility (custom implementation)

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Bundle size increase** | Medium | Low | Chart.js is ~180KB, acceptable for statistics page. Consider code splitting if needed. |
| **Svelte 5 compatibility issues** | Low | High | `svelte-chartjs` v4 officially supports Svelte 5 runes. Test thoroughly. |
| **DaisyUI theme color mismatches** | Medium | Medium | Use CSS variable lookup (§5.1). Test with multiple themes. |
| **Breaking existing page layout** | Low | Medium | Use same card structure, only replace chart internals. |
| **Tooltip formatting inconsistencies** | Medium | Low | Reuse existing `formatNumber()` and `formatMonthLabel()` functions. |
| **Mobile responsiveness issues** | Low | Medium | Chart.js is responsive by default. Test on real devices. |
| **Dark mode rendering problems** | Medium | Medium | Chart.js supports CSS variables. Test theme switching. |

**Overall Risk Level: LOW** — Well-established library with good Svelte integration.

---

## 12. Success Criteria

### Definition of Done:

✅ **Functional:**
- [ ] All three line charts render correctly with live data
- [ ] Hover tooltips display formatted values
- [ ] Charts are responsive across desktop/tablet/mobile
- [ ] Dark mode works without visual glitches

✅ **Code Quality:**
- [ ] Old SVG code removed (functions + markup)
- [ ] New `LineChart.svelte` component is reusable
- [ ] No TypeScript errors or linter warnings
- [ ] Code follows existing project conventions

✅ **Visual:**
- [ ] Charts match or exceed old design quality
- [ ] Colors use correct DaisyUI theme tokens
- [ ] Axes are properly aligned with data points
- [ ] Empty states handled gracefully

✅ **Performance:**
- [ ] Page load time not significantly increased (< 200ms delta)
- [ ] No console errors or warnings
- [ ] Bundle size increase acceptable (< 300KB)

✅ **Testing:**
- [ ] Manual testing checklist completed (§8.1)
- [ ] Cross-browser testing passed
- [ ] Edge cases verified

---

## 13. Timeline Estimate

**Assuming single developer, moderate familiarity with SvelteKit:**

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| **Setup** | Install deps, create component skeleton | 30 minutes |
| **Component Development** | Build `LineChart.svelte` with Chart.js config | 2 hours |
| **Integration** | Replace all 3 charts in statistics page | 1 hour |
| **Styling** | Fine-tune colors, fonts, spacing | 1 hour |
| **Testing** | Manual testing, edge cases, cross-browser | 1.5 hours |
| **Code Cleanup** | Remove old code, refactor | 30 minutes |
| **Documentation** | Update this plan with actual outcomes | 30 minutes |

**Total: ~7 hours** (approximately 1 full work day)

**Adjust if:**
- First time using Chart.js: +2 hours learning curve
- Extensive custom styling needed: +1-2 hours
- Automated tests required: +3-4 hours

---

## 14. Implementation Notes

### 14.1 Chart.js Configuration Template

**For reference when building `LineChart.svelte`:**

```typescript
const config = {
  type: 'line',
  data: {
    labels: props.labels,
    datasets: [{
      label: props.label,
      data: props.data,
      borderColor: getDaisyUIColor(props.color),
      backgroundColor: getDaisyUIColor(props.color) + '33', // 20% opacity
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.1 // slight curve for aesthetics
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false }, // already have card title
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = context.parsed.y;
            return `${context.dataset.label}: ${formatNumber(value, props.locale)}`;
          }
        }
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          callback: (value) => formatNumber(value, props.locale)
        }
      }
    }
  }
};
```

### 14.2 Handling Empty Data

If `points.length === 0`, render placeholder instead of chart:

```svelte
{#if data.length === 0}
  <div class="flex items-center justify-center h-40 text-base-content/50">
    <p>{$_('statistics.noData')}</p>
  </div>
{:else}
  <Line {data} {options} />
{/if}
```

### 14.3 Locale-Aware Number Formatting

Reuse existing `formatNumber()` function from statistics page:

```typescript
// In LineChart.svelte props:
interface Props {
  // ... other props
  formatNumber?: (value: number) => string;
}

// In +page.svelte, pass formatter:
<LineChart
  formatNumber={(val) => formatNumber(val, 0)}
  {/* other props */}
/>
```

---

## 15. References

### Documentation Links

- **Chart.js Docs:** https://www.chartjs.org/docs/latest/
- **svelte-chartjs GitHub:** https://github.com/SauravKanchan/svelte-chartjs
- **DaisyUI Colors:** https://daisyui.com/docs/colors/
- **SvelteKit Docs:** https://svelte.dev/docs/kit/introduction

### Example Projects

- **Chart.js + Svelte 5:** Search GitHub for `svelte-chartjs` + `"svelte": "^5"`
- **DaisyUI Themed Charts:** Look for projects combining DaisyUI + Chart.js

### Alternative Libraries (For Future Reference)

- **LayerChart:** https://layerchart.com/ (Svelte-native, modern)
- **Victory:** https://formidable.com/open-source/victory/ (React, but good API reference)
- **Recharts:** https://recharts.org/ (React-only, but excellent UX patterns to study)

---

## Appendix: File Structure After Implementation

```
frontend/
├── src/
│   ├── lib/
│   │   ├── components/
│   │   │   └── LineChart.svelte          ← NEW (reusable chart component)
│   │   ├── types.ts                      (no changes)
│   │   └── utils/
│   │       └── language.ts               (no changes)
│   └── routes/
│       └── statistics/
│           └── +page.svelte              ← MODIFIED (replace SVG with LineChart)
├── package.json                          ← MODIFIED (add chart.js, svelte-chartjs)
├── package-lock.json                     ← MODIFIED (auto-updated)
└── [other config files unchanged]
```

**Total new files:** 1 (`LineChart.svelte`)  
**Modified files:** 2 (`package.json`, `+page.svelte`)  
**Deleted files:** 0 (only code removal within files)

---

## Conclusion

This plan provides a **low-risk, incremental approach** to replacing self-built SVG charts with Chart.js. The chosen library is production-ready, actively maintained, and requires minimal configuration to integrate with the existing SvelteKit + DaisyUI stack.

**Key Advantages:**
1. Professional hover tooltips and UX
2. Proper axis alignment (Chart.js handles layout automatically)
3. Responsive and mobile-friendly out-of-the-box
4. Minimal code changes (no API modifications needed)
5. Reusable component for future charts

**Next Steps:**
1. Review and approve this plan
2. Execute Phase 1 (Setup) to validate Chart.js integration
3. Proceed with Phase 2-3 if no blockers found
4. Test thoroughly before deploying to production

**Estimated Effort:** 1 full work day (~7 hours) for a developer familiar with SvelteKit.

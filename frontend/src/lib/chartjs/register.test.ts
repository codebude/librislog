import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';
import { _adapters } from 'chart.js';
import '#lib/chartjs/register.js';
import { getTimezone, setTimezone } from '#lib/stores/timezone.js';

// Minimal shape of the dayjs-based date adapter installed by register.ts.
type DateAdapter = {
	add(time: number, amount: number, unit: string): number;
	startOf(time: number, unit: string, weekday?: number): number;
	endOf(time: number, unit: string): number;
};

// `_adapters._date` is the DateAdapterBase class, and the static override() in
// register.ts patches its prototype, so a plain instance exposes the adapter.
const adapter = new (_adapters._date as unknown as new () => DateAdapter)();

const TICK_LIMIT = 1000;
const originalProfileTz = getTimezone();

// The freeze only reproduced when the device time zone and the profile time
// zone were the same fall-back zone, so pin both for this file. Otherwise a
// CI machine in, say, Europe/Berlin never hits the broken dayjs path.
beforeAll(() => {
	vi.stubEnv('TZ', 'America/New_York');
	setTimezone('America/New_York');
});

afterAll(() => {
	vi.unstubAllEnvs();
	setTimezone(originalProfileTz);
});

function hourlyTicks(min: number, max: number): { ticks: number[]; next: number } {
	const ticks: number[] = [];
	let time = adapter.startOf(min, 'hour');
	while (time < max && ticks.length < TICK_LIMIT) {
		ticks.push(time);
		time = adapter.add(time, 1, 'hour');
	}
	return { ticks, next: time };
}

function expectStrictlyIncreasing(values: number[]) {
	for (let i = 1; i < values.length; i++) {
		expect(values[i]).toBeGreaterThan(values[i - 1]);
	}
}

describe('chartjs dayjs date adapter across DST transitions', () => {
	// 2026-11-01 01:00-02:00 America/New_York happens twice because clocks
	// fall back from 02:00 EDT to 01:00 EST.
	const firstOneAm = Date.UTC(2026, 10, 1, 5, 0); // 01:00 EDT
	const secondOneAm = Date.UTC(2026, 10, 1, 6, 0); // 01:00 EST
	const firstHalfPastOne = Date.UTC(2026, 10, 1, 5, 30); // 01:30 EDT
	const secondHalfPastOne = Date.UTC(2026, 10, 1, 6, 30); // 01:30 EST

	it('runs with the pinned New York device and profile time zones', () => {
		// If the TZ pin silently stops working, the tick-loop tests below would
		// pass vacuously on the old adapter, so assert the premise loudly.
		expect(new Date(firstOneAm).getTimezoneOffset()).toBe(240); // EDT
		expect(new Date(secondOneAm).getTimezoneOffset()).toBe(300); // EST
		expect(getTimezone()).toBe('America/New_York');
	});

	it('add() always moves forward inside the repeated hour', () => {
		expect(adapter.add(firstOneAm, 1, 'hour')).toBe(secondOneAm);
		expect(adapter.add(secondOneAm, 1, 'hour')).toBe(Date.UTC(2026, 10, 1, 7, 0));
		// A minute step from 01:59 EDT must land on 01:00 EST, not go backwards.
		expect(adapter.add(Date.UTC(2026, 10, 1, 5, 59), 1, 'minute')).toBe(secondOneAm);
	});

	it('startOf() rounds down to the local hour boundary of the instant', () => {
		expect(adapter.startOf(firstHalfPastOne, 'hour')).toBe(firstOneAm);
		expect(adapter.startOf(secondHalfPastOne, 'hour')).toBe(secondOneAm);
		// Already on a boundary: must not jump to the previous occurrence.
		expect(adapter.startOf(secondOneAm, 'hour')).toBe(secondOneAm);
	});

	it('endOf() ends the hour containing the instant', () => {
		expect(adapter.endOf(secondHalfPastOne, 'hour')).toBe(Date.UTC(2026, 10, 1, 6, 59, 59, 999));
	});

	it('startOf() and endOf() keep local boundaries in a non-whole-hour zone', () => {
		setTimezone('Asia/Kolkata');
		try {
			// 12:15 IST floors to 12:00 IST and ends at 12:59:59.999 IST.
			expect(adapter.startOf(Date.UTC(2026, 10, 1, 6, 45), 'hour')).toBe(Date.UTC(2026, 10, 1, 6, 30));
			expect(adapter.endOf(Date.UTC(2026, 10, 1, 6, 45), 'hour')).toBe(Date.UTC(2026, 10, 1, 7, 29, 59, 999));
		} finally {
			setTimezone('America/New_York');
		}
	});

	it('add() keeps local wall-clock time for calendar units', () => {
		// After the fall-back, a fixed 24h step would land at 23:00 instead of
		// local midnight, which drifts day and month ticks.
		expect(adapter.add(Date.UTC(2026, 9, 31, 4, 0), 1, 'day')).toBe(Date.UTC(2026, 10, 1, 4, 0));
		expect(adapter.add(Date.UTC(2026, 10, 1, 4, 0), 1, 'day')).toBe(Date.UTC(2026, 10, 2, 5, 0));
		expect(adapter.add(Date.UTC(2026, 9, 1, 4, 0), 1, 'month')).toBe(Date.UTC(2026, 10, 1, 4, 0));
		expect(adapter.add(Date.UTC(2026, 10, 1, 4, 0), 1, 'month')).toBe(Date.UTC(2026, 11, 1, 5, 0));
		expect(adapter.add(Date.UTC(2026, 10, 2, 5, 0), -1, 'day')).toBe(Date.UTC(2026, 10, 1, 4, 0));
	});

	it('generates a finite, strictly increasing sequence across the fall-back', () => {
		// The reproduction data from the bug report: a book started 2026-10-31
		// 18:59 UTC and read until 2026-11-01 17:04 UTC with a New York profile.
		const min = Date.UTC(2026, 9, 31, 18, 59);
		const max = Date.UTC(2026, 10, 1, 17, 4);
		const { ticks, next } = hourlyTicks(min, max);

		// Before the fix the loop got stuck at 05:00Z and never reached max.
		expect(ticks.length).toBeLessThan(TICK_LIMIT);
		expect(next).toBeGreaterThanOrEqual(max);
		expectStrictlyIncreasing(ticks);
		// Both real 01:00 instants must be present, the repeated hour is not skipped.
		expect(ticks).toContain(firstOneAm);
		expect(ticks).toContain(secondOneAm);
	});

	it('generates a finite, strictly increasing sequence across spring-forward', () => {
		// 2026-03-08 02:00 America/New_York does not exist, so the step from
		// 01:00 EST goes straight to 03:00 EDT.
		const min = Date.UTC(2026, 2, 8, 4, 0); // 23:00 EST on Mar 7
		const max = Date.UTC(2026, 2, 8, 12, 0); // 08:00 EDT on Mar 8
		const { ticks, next } = hourlyTicks(min, max);

		expect(ticks.length).toBeLessThan(TICK_LIMIT);
		expect(next).toBeGreaterThanOrEqual(max);
		expectStrictlyIncreasing(ticks);
		expect(ticks).toContain(Date.UTC(2026, 2, 8, 6, 0)); // 01:00 EST
		expect(ticks).toContain(Date.UTC(2026, 2, 8, 7, 0)); // 03:00 EDT
	});
});

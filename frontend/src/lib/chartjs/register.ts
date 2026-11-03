import {
	Chart,
	_adapters,
	Title,
	Tooltip,
	Legend,
	BarElement,
	LineElement,
	PointElement,
	CategoryScale,
	LinearScale,
	TimeScale
} from 'chart.js';
import zoomPlugin from 'chartjs-plugin-zoom';
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix';

Chart.register(
	Title,
	Tooltip,
	Legend,
	BarElement,
	LineElement,
	PointElement,
	CategoryScale,
	LinearScale,
	TimeScale,
	zoomPlugin,
	MatrixController,
	MatrixElement
);

import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import advancedFormat from 'dayjs/plugin/advancedFormat';
import localizedFormat from 'dayjs/plugin/localizedFormat';
import quarterOfYear from 'dayjs/plugin/quarterOfYear';
import weekday from 'dayjs/plugin/weekday';
import { getTimezone } from '#lib/stores/timezone.js';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(customParseFormat);
dayjs.extend(advancedFormat);
dayjs.extend(localizedFormat);
dayjs.extend(quarterOfYear);
dayjs.extend(weekday);

// Sub-day units are fixed-length durations. Chart.js advances its tick loop
// with add(), so these must be computed on the epoch value: dayjs's zoned
// arithmetic can stall or step backwards inside a DST fall-back, which makes
// the tick loop run forever and freezes the browser.
const SUB_DAY_UNIT_MS: Record<string, number> = {
	millisecond: 1,
	ms: 1,
	second: 1_000,
	s: 1_000,
	minute: 60_000,
	m: 60_000,
	hour: 3_600_000,
	h: 3_600_000
};

function subDayUnitMs(unit: string): number | undefined {
	const key = unit.toLowerCase();
	return Object.hasOwn(SUB_DAY_UNIT_MS, key) ? SUB_DAY_UNIT_MS[key] : undefined;
}

function zoneOffsetMs(time: number): number {
	return dayjs.utc(time).tz(getTimezone()).utcOffset() * 60_000;
}

function positiveModulo(value: number, divisor: number): number {
	return ((value % divisor) + divisor) % divisor;
}

function startOfLocalUnit(time: number, unitMs: number): number {
	return time - positiveModulo(time + zoneOffsetMs(time), unitMs);
}

const FORMATS: Record<string, string> = {
	datetime: 'MMM D, YYYY, h:mm:ss a',
	millisecond: 'h:mm:ss.SSS a',
	second: 'h:mm:ss a',
	minute: 'h:mm a',
	hour: 'hA',
	day: 'MMM D',
	week: 'll',
	month: 'MMM YYYY',
	quarter: '[Q]Q - YYYY',
	year: 'YYYY'
};

_adapters._date.override({
	_create: (time: number | string | Date) => dayjs.utc(time).valueOf(),
	formats: () => FORMATS,
	parse: (value: unknown, format?: string) => {
		if (value === null || value === undefined) return null;
		if (typeof value === 'string' && format) {
			const d = dayjs.utc(value, format);
			return d.isValid() ? d.valueOf() : null;
		}
		const d = dayjs.utc(value as string | number | Date);
		return d.isValid() ? d.valueOf() : null;
	},
	format: (time: unknown, format: string) => dayjs.utc(time as number).tz(getTimezone()).format(format),
	add: (time: unknown, amount: number, unit: string) => {
		const t = time as number;
		const size = subDayUnitMs(unit);
		if (size !== undefined) {
			return t + amount * size;
		}
		return dayjs.utc(t).tz(getTimezone()).add(amount, unit as dayjs.ManipulateType).valueOf();
	},
	diff: (max: unknown, min: unknown, unit: string) => dayjs.utc(max as number).tz(getTimezone()).diff(dayjs.utc(min as number).tz(getTimezone()), unit as dayjs.OpUnitType),
	startOf: (time: unknown, unit: string, weekday?: number) => {
		const t = time as number;
		const size = subDayUnitMs(unit);
		if (size !== undefined) {
			return startOfLocalUnit(t, size);
		}
		const date = dayjs.utc(t).tz(getTimezone());
		if (unit === 'isoWeek') {
			return (date as unknown as { weekday: (w: number) => { valueOf: () => number } }).weekday(weekday ?? 1).valueOf();
		}
		return date.startOf(unit as dayjs.OpUnitType).valueOf();
	},
	endOf: (time: unknown, unit: string) => {
		const t = time as number;
		const size = subDayUnitMs(unit);
		if (size !== undefined) {
			return startOfLocalUnit(t, size) + size - 1;
		}
		return dayjs.utc(t).tz(getTimezone()).endOf(unit as dayjs.OpUnitType).valueOf();
	},
} as unknown as Parameters<typeof _adapters._date.override>[0]);

export { Chart as ChartJS };

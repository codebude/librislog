import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(timezone);

export function toDateInputValue(value: string | null | undefined, timeZone: string): string {
	if (!value) return '';
	const d = dayjs(value);
	if (!d.isValid()) return '';
	return d.tz(timeZone).format('YYYY-MM-DD');
}

export function fromDateInputValue(value: string, timeZone: string): string | null {
	const trimmed = value.trim();
	if (!trimmed) return null;
	const d = dayjs.tz(trimmed, timeZone);
	if (!d.isValid()) return null;
	return d.toISOString();
}

export function formatDate(value: string | null | undefined, timeZone: string): string {
	return toDateInputValue(value, timeZone);
}

export function formatDateTime(value: string | null | undefined, timeZone: string): string {
	if (!value) return '';
	const d = dayjs(value);
	if (!d.isValid()) return '';
	return d.tz(timeZone).format('YYYY-MM-DD HH:mm');
}

export function today(timeZone: string): string {
	return dayjs().tz(timeZone).format('YYYY-MM-DD');
}

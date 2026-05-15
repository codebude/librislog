import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(timezone);

function guessTimezone(): string {
	return dayjs.tz.guess() || 'UTC';
}

let _timezone: string = guessTimezone();

export function setTimezone(tz: string) {
	_timezone = tz;
}

export function getTimezone(): string {
	return _timezone;
}

export function detectTimezone(): string {
	return guessTimezone();
}

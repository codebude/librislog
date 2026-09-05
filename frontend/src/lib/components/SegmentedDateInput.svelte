<script lang="ts">
	type DateField = 'day' | 'month' | 'year';

	let {
		value = $bindable(''),
		invalid = $bindable(false),
		hasInput = $bindable(false),
		name = '',
		min = undefined,
		max = undefined,
		disabled = false,
		required = false,
		inputClass = 'input input-bordered input-sm w-full',
		ariaLabel = ''
	}: {
		value?: string;
		invalid?: boolean;
		hasInput?: boolean;
		name?: string;
		min?: string;
		max?: string;
		disabled?: boolean;
		required?: boolean;
		inputClass?: string;
		ariaLabel?: string;
	} = $props();

	const sampleDate = new Date(Date.UTC(2001, 10, 22));
	const localizedParts = new Intl.DateTimeFormat(undefined, {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	}).formatToParts(sampleDate);

	const fieldOrder: DateField[] = localizedParts
		.filter((part) => part.type === 'day' || part.type === 'month' || part.type === 'year')
		.map((part) => part.type as DateField);

	const separators = localizedParts
		.filter((part) => part.type === 'literal')
		.map((part) => part.value)
		.slice(0, 2);

	let containerEl: HTMLDivElement | undefined = $state();
	let day = $state('');
	let month = $state('');
	let year = $state('');
	let isEditing = $state(false);
	let ignoreNextExternalSync = false;

	function fieldValue(field: DateField): string {
		if (field === 'day') return day;
		if (field === 'month') return month;
		return year;
	}

	function setFieldValue(field: DateField, next: string) {
		if (field === 'day') day = next;
		else if (field === 'month') month = next;
		else year = next;
	}

	function fieldMaxLength(field: DateField): number {
		return field === 'year' ? 4 : 2;
	}

	function fieldPlaceholder(field: DateField): string {
		if (field === 'day') return 'DD';
		if (field === 'month') return 'MM';
		return 'YYYY';
	}

	function fieldAriaLabel(field: DateField): string {
		if (field === 'day') return 'Day';
		if (field === 'month') return 'Month';
		return 'Year';
	}

	function sanitizeDigits(input: string, maxLen: number): string {
		return input.replace(/\D/g, '').slice(0, maxLen);
	}

	function isValidIsoDate(iso: string): boolean {
		const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
		if (!match) return false;
		const y = Number(match[1]);
		const m = Number(match[2]);
		const d = Number(match[3]);
		if (m < 1 || m > 12 || d < 1 || d > 31) return false;
		const dt = new Date(Date.UTC(y, m - 1, d));
		return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
	}

	function isWithinRange(iso: string): boolean {
		if (min && iso < min) return false;
		if (max && iso > max) return false;
		return true;
	}

	function setBoundValue(next: string) {
		if (value === next) return;
		ignoreNextExternalSync = true;
		value = next;
	}

	function allPartsEmpty(): boolean {
		return day === '' && month === '' && year === '';
	}

	function updateValueFromParts(options: { markIncompleteInvalid?: boolean } = {}) {
		hasInput = !allPartsEmpty();
		invalid = false;
		if (allPartsEmpty()) {
			setBoundValue('');
			return;
		}

		if (!day || !month || !year || year.length !== 4) {
			invalid = options.markIncompleteInvalid ?? false;
			setBoundValue('');
			return;
		}

		const iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
		if (!isValidIsoDate(iso) || !isWithinRange(iso)) {
			invalid = true;
			setBoundValue('');
			return;
		}

		setBoundValue(iso);
	}

	function syncFromIso(nextValue: string) {
		if (!nextValue) {
			// Don't clear fields if we're in an invalid+hasInput state
			// This allows users to see and correct their invalid input
			if (invalid && hasInput) {
				return;
			}
			day = '';
			month = '';
			year = '';
			invalid = false;
			hasInput = false;
			return;
		}

		const match = nextValue.match(/^(\d{4})-(\d{2})-(\d{2})$/);
		if (!match) {
			day = '';
			month = '';
			year = '';
			invalid = false;
			hasInput = false;
			return;
		}

		year = match[1];
		month = match[2];
		day = match[3];
		invalid = false;
		hasInput = true;
	}

	function formattedDateForClipboard(): string {
		const partMap: Record<DateField, string> = {
			day: day ? day.padStart(2, '0') : '',
			month: month ? month.padStart(2, '0') : '',
			year
		};
		const ordered = fieldOrder.map((field) => partMap[field]);
		if (ordered.some((part) => !part)) return '';
		return `${ordered[0]}${separators[0] ?? '/'}${ordered[1]}${separators[1] ?? '/'}${ordered[2]}`;
	}

	function copyEntireDate() {
		const formatted = formattedDateForClipboard();
		if (!formatted) return false;
		if (navigator.clipboard?.writeText) {
			void navigator.clipboard.writeText(formatted);
			return true;
		}
		return false;
	}

	function normalizeFieldOnBlur(field: DateField) {
		const current = fieldValue(field);
		if (!current) {
			updateValueFromParts({ markIncompleteInvalid: true });
			return;
		}
		if ((field === 'day' || field === 'month') && current.length === 1) {
			setFieldValue(field, current.padStart(2, '0'));
		}
		updateValueFromParts({ markIncompleteInvalid: true });
	}

	function focusFieldByIndex(index: number) {
		const field = fieldOrder[index];
		if (!field || !containerEl) return;
		const target = containerEl.querySelector<HTMLInputElement>(`input[data-field="${field}"]`);
		target?.focus();
		target?.select();
	}

	function handleKeydown(field: DateField, index: number, event: KeyboardEvent) {
		const key = event.key;
		const lowerKey = key.toLowerCase();

		if ((event.ctrlKey || event.metaKey) && lowerKey === 'c') {
			if (copyEntireDate()) {
				event.preventDefault();
			}
			return;
		}

		if (key === 'Tab') {
			if (event.shiftKey) {
				if (index > 0) {
					event.preventDefault();
					focusFieldByIndex(index - 1);
				}
				return;
			}
			if (index < fieldOrder.length - 1) {
				event.preventDefault();
				focusFieldByIndex(index + 1);
			}
			return;
		}

		if (key === 'ArrowRight') {
			const target = event.currentTarget as HTMLInputElement;
			if (target.selectionStart === target.value.length && index < fieldOrder.length - 1) {
				event.preventDefault();
				focusFieldByIndex(index + 1);
			}
			return;
		}

		if (key === 'ArrowLeft') {
			const target = event.currentTarget as HTMLInputElement;
			if ((target.selectionStart ?? 0) === 0 && index > 0) {
				event.preventDefault();
				focusFieldByIndex(index - 1);
			}
			return;
		}

		if (key === '.' || key === '/' || key === '-') {
			if (index < fieldOrder.length - 1) {
				event.preventDefault();
				focusFieldByIndex(index + 1);
			}
			return;
		}

		const isDigit = /^\d$/.test(key);
		const allowed =
			isDigit ||
			key === 'Backspace' ||
			key === 'Delete' ||
			key === 'Home' ||
			key === 'End' ||
			key === 'Enter' ||
			key === 'Escape' ||
			key.startsWith('Arrow') ||
			event.ctrlKey ||
			event.metaKey;

		if (!allowed) {
			event.preventDefault();
		}
	}

	function parsePastedDate(raw: string): { day: string; month: string; year: string } | null {
		const compact = raw.trim();
		if (!compact) return null;

		const compactDigits = compact.replace(/\D/g, '');
		if (compactDigits.length === 8) {
			if (compactDigits.slice(0, 4).match(/^(19|20)\d{2}$/)) {
				const yearPart = compactDigits.slice(0, 4);
				const monthPart = compactDigits.slice(4, 6);
				const dayPart = compactDigits.slice(6, 8);
				const iso = `${yearPart}-${monthPart}-${dayPart}`;
				if (isValidIsoDate(iso) && isWithinRange(iso)) {
					return { day: dayPart, month: monthPart, year: yearPart };
				}
			}
		}

		const numbers = compact.match(/\d+/g);
		if (!numbers || numbers.length < 3) return null;

		const [first, second, third] = numbers;
		let parsedYear = '';
		let parsedMonth = '';
		let parsedDay = '';

		if (first.length === 4) {
			parsedYear = first;
			parsedMonth = second;
			parsedDay = third;
		} else if (third.length === 4) {
			const mapped: Record<DateField, string> = { day: '', month: '', year: '' };
			mapped[fieldOrder[0] ?? 'day'] = first;
			mapped[fieldOrder[1] ?? 'month'] = second;
			mapped[fieldOrder[2] ?? 'year'] = third;
			parsedYear = mapped.year;
			parsedMonth = mapped.month;
			parsedDay = mapped.day;
		} else {
			return null;
		}

		if (parsedYear.length !== 4) return null;
		const monthNum = Number(parsedMonth);
		const dayNum = Number(parsedDay);
		if (!Number.isFinite(monthNum) || !Number.isFinite(dayNum)) return null;

		const monthPart = String(monthNum).padStart(2, '0');
		const dayPart = String(dayNum).padStart(2, '0');
		const iso = `${parsedYear}-${monthPart}-${dayPart}`;
		if (!isValidIsoDate(iso) || !isWithinRange(iso)) return null;

		return {
			day: dayPart,
			month: monthPart,
			year: parsedYear
		};
	}

	function handlePaste(field: DateField, event: ClipboardEvent) {
		const pasted = event.clipboardData?.getData('text') ?? '';
		const parsed = parsePastedDate(pasted);
		if (parsed) {
			event.preventDefault();
			day = parsed.day;
			month = parsed.month;
			year = parsed.year;
			updateValueFromParts();
			return;
		}

		const fallback = sanitizeDigits(pasted, fieldMaxLength(field));
		if (fallback) {
			event.preventDefault();
			setFieldValue(field, fallback);
			updateValueFromParts();
		}
	}

	function handleInput(field: DateField, event: Event) {
		const target = event.currentTarget as HTMLInputElement;
		const sanitized = sanitizeDigits(target.value, fieldMaxLength(field));
		setFieldValue(field, sanitized);
		updateValueFromParts();
	}

	function handleFocusIn() {
		isEditing = true;
	}

	function handleFocusOut() {
		setTimeout(() => {
			if (!containerEl?.contains(document.activeElement)) {
				isEditing = false;
			}
		}, 0);
	}

	$effect(() => {
		const externalValue = value;
		if (ignoreNextExternalSync) {
			ignoreNextExternalSync = false;
			return;
		}
		if (isEditing) return;
		syncFromIso(externalValue);
	});
</script>

<div
	bind:this={containerEl}
	class={`${inputClass} flex items-center gap-1 px-2 ${invalid ? 'border-error' : ''}`}
	onfocusin={handleFocusIn}
	onfocusout={handleFocusOut}
>
	{#each fieldOrder as field, idx}
		<input
			type="text"
			data-field={field}
			inputmode="numeric"
			autocomplete="off"
			spellcheck="false"
			class={`bg-transparent border-0 outline-none text-center text-sm ${field === 'year' ? 'w-14' : 'w-8'}`}
			value={fieldValue(field)}
			placeholder={fieldPlaceholder(field)}
			maxlength={fieldMaxLength(field)}
			{disabled}
			{required}
			aria-label={idx === 0 ? (ariaLabel || undefined) : fieldAriaLabel(field)}
			oninput={(event) => handleInput(field, event)}
			onkeydown={(event) => handleKeydown(field, idx, event)}
			onblur={() => normalizeFieldOnBlur(field)}
			onpaste={(event) => handlePaste(field, event)}
		/>
		{#if idx < fieldOrder.length - 1}
			<span class="select-none text-base-content/60">{separators[idx] ?? '/'}</span>
		{/if}
	{/each}
	<input type="hidden" {name} value={value} />
</div>

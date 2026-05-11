export interface PasswordChecks {
	minLength: boolean;
	hasUppercase: boolean;
	hasLowercase: boolean;
	hasNumber: boolean;
	hasSpecial: boolean;
}

export function getPasswordChecks(password: string): PasswordChecks {
	return {
		minLength: password.length >= 8,
		hasUppercase: /[A-Z]/.test(password),
		hasLowercase: /[a-z]/.test(password),
		hasNumber: /\d/.test(password),
		hasSpecial: /[^A-Za-z0-9\s]/.test(password)
	};
}

export function passwordChecksPassed(checks: PasswordChecks): boolean {
	return checks.minLength && checks.hasUppercase && checks.hasLowercase && checks.hasNumber && checks.hasSpecial;
}

export function passwordStrengthPercent(checks: PasswordChecks): number {
	const passed = Object.values(checks).filter(Boolean).length;
	return Math.round((passed / 5) * 100);
}

export function passwordStrengthClass(checks: PasswordChecks): string {
	const passed = Object.values(checks).filter(Boolean).length;
	if (passed <= 2) return 'progress-error';
	if (passed <= 4) return 'progress-warning';
	return 'progress-success';
}

export function complexityRequirementLabels(t: (key: string) => string): Array<{ key: keyof PasswordChecks; label: string }> {
	return [
		{ key: 'minLength', label: t('password.minLength') },
		{ key: 'hasUppercase', label: t('password.uppercase') },
		{ key: 'hasLowercase', label: t('password.lowercase') },
		{ key: 'hasNumber', label: t('password.number') },
		{ key: 'hasSpecial', label: t('password.special') }
	];
}

export const passwordPattern = '(?=.*\\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9\\s]).{8,}';

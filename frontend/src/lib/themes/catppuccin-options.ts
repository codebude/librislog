/**
 * Shared overrides for the Catppuccin daisyUI port.
 *
 * LibrisLog uses `secondary` for chart series, secondary buttons and the
 * add-book stripe. The port maps it to a surface tone (surface0), which
 * blends into the page background, so every flavor uses `mauve` instead.
 */
export const CATPPUCCIN_OPTIONS = {
	secondary: 'mauve',
	'secondary-content': 'base'
} as const;

/**
 * Latte is the only light flavor. The upstream port paints the content colors
 * light (mantle/base), which drops button and badge labels on the pale accents
 * to roughly 2:1 in WCAG contrast.
 *
 * These overrides keep the palette but choose the higher-contrast token per
 * accent, and `blue` instead of lavender for primary so the main action keeps
 * a legible label. Resulting contrast for text on the accent: primary 4.34:1,
 * secondary 4.79:1, neutral 3.49:1, accent 3.02:1, warning 3.05:1,
 * error 4.80:1, info 2.86:1, success 2.96:1. Info and success stay just below
 * 3:1 because that is the highest-contrast palette token available; the dark
 * flavors keep the port defaults, which range from 4.09:1 to 13.86:1.
 */
export const CATPPUCCIN_LATTE_OPTIONS = {
	...CATPPUCCIN_OPTIONS,
	primary: 'blue',
	'primary-content': 'base',
	neutral: 'overlay2',
	'neutral-content': 'base',
	'accent-content': 'text',
	'success-content': 'base',
	'warning-content': 'text',
	'error-content': 'base',
	'info-content': 'text'
} as const;

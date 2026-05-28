const PY_KEYWORDS = new Set([
	'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
	'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
	'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
	'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
	'try', 'while', 'with', 'yield'
]);

const TOKENS: Array<{ re: RegExp; cls: string }> = [
	{ re: /#[^\n]*/g, cls: 'comment' },
	{ re: /'''[\s\S]*?'''|"""[\s\S]*?"""/g, cls: 'string' },
	{ re: /'[^'\\]*(?:\\.[^'\\]*)*'|"[^"\\]*(?:\\.[^"\\]*)*"/g, cls: 'string' },
	{ re: /\b[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b/g, cls: 'number' },
	{ re: /\b[a-zA-Z_]\w*(?=\s*\()/g, cls: 'function' },
	{ re: /\b[a-zA-Z_]\w*\b/g, cls: 'keyword' },
];

export function highlightPython(code: string): string {
	let html = '';
	let last = 0;
	const segments: Array<[number, number, string]> = [];

	for (const { re, cls } of TOKENS) {
		re.lastIndex = 0;
		let m: RegExpExecArray | null;
		while ((m = re.exec(code)) !== null) {
			if (cls === 'keyword' && !PY_KEYWORDS.has(m[0])) continue;
			segments.push([m.index, m.index + m[0].length, cls]);
		}
	}

	segments.sort((a, b) => a[0] - b[0] || (b[1] - b[0]) - (a[1] - a[0]));

	const merged: Array<[number, number, string]> = [];
	for (const seg of segments) {
		if (merged.length > 0 && seg[0] < merged[merged.length - 1][1]) continue;
		merged.push(seg);
	}

	for (const [start, end, cls] of merged) {
		if (start > last) {
			html += esc(code.slice(last, start));
		}
		html += `<span class="hl-${cls}">${esc(code.slice(start, end))}</span>`;
		last = end;
	}
	if (last < code.length) {
		html += esc(code.slice(last));
	}
	return html;
}

const JSON_TOKENS: Array<{ re: RegExp; cls: string }> = [
	{ re: /"[^"\\]*(?:\\.[^"\\]*)?"\s*:/g, cls: 'json-key' },
	{ re: /"[^"\\]*(?:\\.[^"\\]*)?"/g, cls: 'json-string' },
	{ re: /\b-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b/g, cls: 'json-number' },
	{ re: /\b(?:true|false|null)\b/g, cls: 'json-bool' },
];

export function highlightJson(code: string): string {
	let html = '';
	let last = 0;
	const segments: Array<[number, number, string]> = [];

	for (const { re, cls } of JSON_TOKENS) {
		re.lastIndex = 0;
		let m: RegExpExecArray | null;
		while ((m = re.exec(code)) !== null) {
			segments.push([m.index, m.index + m[0].length, cls]);
		}
	}

	segments.sort((a, b) => a[0] - b[0] || (b[1] - b[0]) - (a[1] - a[0]));

	const merged: Array<[number, number, string]> = [];
	for (const seg of segments) {
		if (merged.length > 0 && seg[0] < merged[merged.length - 1][1]) continue;
		merged.push(seg);
	}

	for (const [start, end, cls] of merged) {
		if (start > last) {
			html += esc(code.slice(last, start));
		}
		html += `<span class="hl-${cls}">${esc(code.slice(start, end))}</span>`;
		last = end;
	}
	if (last < code.length) {
		html += esc(code.slice(last));
	}
	return html;
}

function esc(s: string): string {
	return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

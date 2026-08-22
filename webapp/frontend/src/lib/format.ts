// Shared formatters. `formatBytes` previously existed in three copies and `escapeHtml` in two.

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB'] as const;

export function formatBytes(bytes: number): string {
	if (!bytes) return '0 B';
	let value = bytes;
	let unitIndex = 0;
	while (value >= 1024 && unitIndex < BYTE_UNITS.length - 1) {
		value /= 1024;
		unitIndex += 1;
	}
	return `${unitIndex === 0 ? value : value.toFixed(1)} ${BYTE_UNITS[unitIndex]}`;
}

/** Elapsed time since a Unix timestamp (seconds), as a compact human string. */
export function formatElapsed(sinceEpochSeconds: number): string {
	const seconds = Math.max(0, Math.round(Date.now() / 1000 - sinceEpochSeconds));
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
	const hours = Math.floor(minutes / 60);
	return `${hours}h ${minutes % 60}m`;
}

/**
 * Escape text for safe interpolation into an HTML string.
 *
 * Solid sets text via the DOM, so components never need this -- it is here only for the few places that
 * genuinely build markup strings (tooltips fed to third-party renderers, Sigma.js label HTML). Prefer
 * passing text as a child over calling this.
 */
export function escapeHtml(value: string): string {
	return value
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

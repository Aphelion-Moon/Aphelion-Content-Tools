/**
 * Join class names, dropping anything falsy.
 *
 * Exists because `noUncheckedIndexedAccess` (kept on -- it catches real array bugs) types every
 * CSS-module lookup as `string | undefined`, which makes Solid's `classList={{ [styles.x]: cond }}`
 * a type error at every use site. Passing the same thing through here reads better than sprinkling
 * non-null assertions, and works identically:
 *
 *     class={cx(styles.pill, isActive && styles.pillActive)}
 */
export function cx(...parts: readonly (string | false | null | undefined)[]): string {
	return parts.filter(Boolean).join(' ');
}

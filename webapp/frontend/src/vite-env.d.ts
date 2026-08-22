/// <reference types="vite/client" />

// `noUncheckedIndexedAccess` is on, which would otherwise type every CSS-module class as
// `string | undefined` and force a non-null assertion at every single use site. A missing class name is
// a build-time authoring mistake, not a runtime condition worth guarding, so declare them as plain
// strings and keep the strictness where it earns its place.
declare module '*.module.css' {
	const classes: Readonly<Record<string, string>>;
	export default classes;
}

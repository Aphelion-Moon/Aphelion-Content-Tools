export interface OwnedPath {
	readonly path: string;
}

export function toggleSelectedPath(selected: readonly string[], path: string): readonly string[] {
	return selected.includes(path) ? selected.filter((candidate) => candidate !== path) : [...selected, path];
}

export function selectedOwnedPaths(selected: readonly string[], owned: readonly OwnedPath[]): readonly string[] {
	const ownedPaths = new Set(owned.map((change) => change.path));
	return selected.filter((path) => ownedPaths.has(path));
}

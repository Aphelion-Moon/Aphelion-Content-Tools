import { lazy, type Component } from 'solid-js';

// THE place a tool is registered. Adding a tool means adding one entry here -- nothing else.
//
// Pre-rewrite, the same facts were spread across nine locations that had to be hand-synchronised: the nav
// markup in five separate HTML files, plus TOOL_ROUTES / TOOL_SCRIPTS / TOOL_STYLES / TOOL_TITLES and
// SEARCH_PAGES in shell.js. They did drift -- the nav order and SEARCH_PAGES order disagreed until a
// reordering pass fixed all six copies by hand.
//
// This mirrors the backend's own `webapp/tool_registry.py` on purpose: one list, no tool importing
// another's code. A tool's `id` means the same thing on both sides.

export interface ToolManifest {
	/** Stable identifier. Matches the backend's tool id where the tool also registers background jobs. */
	readonly id: string;
	/** Route path, used by the router and by nav links. */
	readonly route: string;
	/** Label shown in the nav pill and in global search results. */
	readonly navLabel: string;
	/** Document title for this route. */
	readonly title: string;
	/** Short description shown under the page heading. */
	readonly description: string;
	/**
	 * Optional per-tool accent, applied as a CSS custom property on the nav pill. Tools without one
	 * inherit the shared palette rather than declaring a duplicate default.
	 */
	readonly accent?: { readonly color: string; readonly contrast: string };
	readonly component: Component;
}

export const TOOLS: readonly ToolManifest[] = [
	{
		id: 'home',
		route: '/',
		navLabel: 'Home',
		title: 'Aphelion Content Tools',
		description: "A local toolkit for authoring and maintaining Meridian-Rift's modular content.",
		accent: { color: '#f2a93c', contrast: '#1f1400' },
		component: lazy(() => import('./home/HomePage')),
	},
	{
		id: 'file-management',
		route: '/file-management',
		navLabel: 'File Management',
		title: 'File Management',
		description:
			'Repository status, local Git actions, game-repository export, and cache/storage management, all in one place.',
		accent: { color: '#3cc9f2', contrast: '#00212b' },
		component: lazy(() => import('./fileManagement/FileManagementPage')),
	},
	{
		id: 'parsec',
		route: '/parsec',
		navLabel: 'Parsec',
		title: 'Parsec',
		description: "Her home page: who she is, how she animates, and what she's said recently.",
		accent: { color: '#ff8fb3', contrast: '#3a0016' },
		component: lazy(() => import('./parsec/ParsecPage')),
	},
	{
		id: 'lore-editor',
		route: '/lore-editor',
		navLabel: 'Lore Editor',
		title: 'Lore Editor',
		description: 'Review catalog content and maintain lore overrides.',
		component: lazy(() => import('./loreEditor/LoreEditorPage')),
	},
	{
		id: 'graph',
		route: '/graph',
		navLabel: 'Content Graph',
		title: 'Content Graph',
		description: 'Visualize modules, master_files overrides, and edit markers.',
		component: lazy(() => import('./contentGraph/ContentGraphPage')),
	},
];

export function toolByRoute(route: string): ToolManifest | undefined {
	return TOOLS.find((tool) => tool.route === route);
}

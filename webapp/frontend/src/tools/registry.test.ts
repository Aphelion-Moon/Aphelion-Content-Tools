import { describe, expect, it } from 'vitest';
import { TOOLS, toolByRoute } from './registry';
import capabilities from '~/lib/tool-capabilities.json';

// These tests exist to protect the property the rewrite was for: a tool is defined in exactly one place.
// If someone reintroduces a parallel list (a second nav array, a hand-kept search index), keeping these
// green requires deriving it from TOOLS -- which is the point.

describe('tool registry', () => {
	it('matches the generated backend capability routes', () => {
		expect(TOOLS.map(({ id, route }) => ({ id, route }))).toEqual(capabilities.map(({ id, route }) => ({ id, route })));
	});
	it('gives every tool a unique id and route', () => {
		expect(new Set(TOOLS.map((tool) => tool.id)).size).toBe(TOOLS.length);
		expect(new Set(TOOLS.map((tool) => tool.route)).size).toBe(TOOLS.length);
	});

	it('gives every tool the fields the shell and router both need', () => {
		for (const tool of TOOLS) {
			expect(tool.id, 'id').toBeTruthy();
			expect(tool.route.startsWith('/'), `${tool.id} route is absolute`).toBe(true);
			expect(tool.navLabel, `${tool.id} navLabel`).toBeTruthy();
			expect(tool.title, `${tool.id} title`).toBeTruthy();
			expect(tool.description, `${tool.id} description`).toBeTruthy();
			expect(typeof tool.component, `${tool.id} component`).toBe('function');
		}
	});

	it('keeps Home at the root so the default route resolves', () => {
		expect(toolByRoute('/')?.id).toBe('home');
	});

	it('orders the nav with Parsec between File Management and Lore Editor', () => {
		// Pre-rewrite this order lived in six hand-synchronised copies and drifted between them.
		expect(TOOLS.map((tool) => tool.id)).toEqual([
			'home',
			'file-management',
			'parsec',
			'lore-editor',
			'outfit-editor',
			'job-editor',
			'graph',
		]);
	});

	it('returns undefined for an unknown route rather than throwing', () => {
		expect(toolByRoute('/nope')).toBeUndefined();
	});
});

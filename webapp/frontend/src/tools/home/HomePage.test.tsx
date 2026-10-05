import { render } from 'solid-js/web';
import { afterEach, describe, expect, it } from 'vitest';
import { setHealth } from '~/store/appStore';
import HomePage from './HomePage';

afterEach(() => {
	setHealth(null);
	document.body.replaceChildren();
});

describe('Home page', () => {
	it('presents the overview as one responsive three-card dashboard', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <HomePage />, host);

		const dashboard = host.querySelector('[aria-label="Content tools overview"]');
		expect(dashboard).not.toBeNull();
		expect(dashboard?.querySelectorAll(':scope > section')).toHaveLength(3);
		dispose();
	});

	it('shows each dataset and never presents a stale game workspace as current', () => {
		setHealth({
			tables: {},
			total_rows: 0,
			disk_bytes: 0,
			last_write_time: null,
			semantic_search: { mode: 'keyword-only', model_id: 'fixture', reason: 'offline' },
			projection: { current: true, reason: null, path: 'store', content_revision: 'lore', active: null },
			workspace: {
				current: false,
				reason: 'The catalog dataset was built from a different game revision.',
				selected_game_revision: 'new-game-revision',
				datasets: [
					{ kind: 'lore', required: true, state: 'current', current: true, source_revision: 'lore' },
					{ kind: 'catalog', required: true, state: 'stale', current: false, source_revision: 'old-game-revision' },
				],
			},
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <HomePage />, host);

		expect(host.textContent).toContain('Workspace stale');
		expect(host.textContent).toContain('catalog: stale');
		expect(host.textContent).not.toContain('Workspace current');
		dispose();
	});
});

import { For, Show, createEffect, createSignal, type JSX } from 'solid-js';
import { A, useLocation } from '@solidjs/router';
import { TOOLS } from '~/tools/registry';
import { cx } from '~/lib/cx';
import GlobalSearch from './GlobalSearch';
import Parsec from './Parsec';
import SharedReferences from './SharedReferences';
import StoreStatus from './StoreStatus';
import styles from './AppShell.module.css';
import missionPatch from '~/assets/meridian/mission-patch.webp';
import { setActiveRoute } from '~/store/appStore';
import { reportParsec } from '~/lib/parsec/coordinator';

interface AppShellProps {
	readonly children?: JSX.Element;
}

/** One route-aware shell and search owner for every current and future tool. */
export default function AppShell(props: AppShellProps) {
	const location = useLocation();
	const activeTool = () => TOOLS.find((tool) => tool.route === location.pathname);
	const [navigationOpen, setNavigationOpen] = createSignal(false);
	let menuButton: HTMLButtonElement | undefined;

	createEffect(() => {
		const route = location.pathname;
		setActiveRoute(route);
		setNavigationOpen(false);
		reportParsec({ type: 'navigation', phase: 'context-changed', tool: null, route, dedupeKey: 'navigation' });
	});

	return (
		<div class={styles.layout} onKeyDown={(event) => {
			if (event.key === 'Escape' && navigationOpen()) {
				setNavigationOpen(false);
				menuButton?.focus();
			}
		}}>
			<a class={styles.skipLink} href="#main-content">Skip to content</a>
			<aside id="application-sidebar" class={styles.sidebar} data-open={navigationOpen()} aria-label="Application sidebar" data-shell-chrome>
				<A href="/" class={styles.brand} aria-label="Meridian — Aphelion Content Tools home">
					<img src={missionPatch} width="110" height="110" alt="" />
					<span class={styles.wordmark}>Meridian</span>
					<span class={styles.stripe} aria-hidden="true" />
					<span class={styles.tagline}>Aphelion Content Tools</span>
				</A>
				<p class={styles.navLabel}>Workspace</p>
				<nav class={styles.nav} aria-label="Tools">
					<For each={TOOLS}>{(tool) => (
						<A href={tool.route} class={cx(styles.pill, location.pathname === tool.route && styles.pillActive)}
							aria-current={location.pathname === tool.route ? 'page' : undefined}
							onClick={() => setNavigationOpen(false)}>{tool.navLabel}</A>
					)}</For>
				</nav>
				<div class={styles.sidebarTools}>
					<StoreStatus />
					<Parsec />
					<SharedReferences />
				</div>
			</aside>
			<div class={styles.workspace}>
				<header class={styles.topbar} aria-label="Workspace header" data-shell-chrome>
					<button ref={menuButton} type="button" class={styles.menu} aria-controls="application-sidebar"
						aria-expanded={navigationOpen()} onClick={() => setNavigationOpen(!navigationOpen())}>
						{navigationOpen() ? 'Close menu' : 'Menu'}
					</button>
					<p class={styles.breadcrumb}>Workspace <span aria-hidden="true">/</span> <span>{activeTool()?.navLabel ?? 'Content Tools'}</span></p>
					<GlobalSearch />
					<a class={styles.siteLink} href="https://meridian.a13.info/about/" target="_blank" rel="noreferrer">Meridian ↗</a>
				</header>
				<main id="main-content" class={styles.content} tabIndex={-1}>
					<header class={styles.hero}>
						<p class={styles.eyebrow}>Aphelion Content Tools</p>
						<h1>{activeTool()?.navLabel ?? 'Aphelion Content Tools'}</h1>
						<Show when={activeTool()}>{(tool) => <p class={styles.description}>{tool().description}</p>}</Show>
					</header>
					{props.children}
				</main>
			</div>
		</div>
	);
}

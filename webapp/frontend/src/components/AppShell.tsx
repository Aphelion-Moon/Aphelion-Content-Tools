import { For, Show, type JSX } from 'solid-js';
import { A, useLocation } from '@solidjs/router';
import { TOOLS, type ToolManifest } from '~/tools/registry';
import { appState } from '~/store/appStore';
import GlobalSearch from './GlobalSearch';
import styles from './AppShell.module.css';

// The single layout. Pre-rewrite this markup was hand-duplicated verbatim across five HTML files, so
// every nav change (adding Parsec, reordering the pills) meant editing all five and keeping them in sync.

interface AppShellProps {
	readonly children?: JSX.Element;
}

function accentStyle(tool: ToolManifest): JSX.CSSProperties | undefined {
	if (!tool.accent) return undefined;
	return { '--pill-accent': tool.accent.color, '--pill-contrast': tool.accent.contrast };
}

export default function AppShell(props: AppShellProps) {
	const location = useLocation();
	const activeTool = () => TOOLS.find((tool) => tool.route === location.pathname);

	return (
		<div class={styles.layout}>
			<aside class={styles.sidebar}>
				<header class={styles.hero}>
					<p class={styles.eyebrow}>Aphelion Content Tools</p>
					<h1>{activeTool()?.navLabel ?? 'Aphelion Content Tools'}</h1>
					<Show when={activeTool()}>{(tool) => <p>{tool().description}</p>}</Show>
				</header>

				<p class={styles.connection}>
					<span classList={{ [styles.dot!]: true, [styles.dotLive!]: appState.connected }} />
					{appState.connected ? 'Live' : 'Reconnecting…'}
				</p>

				<GlobalSearch />

				<nav class={styles.nav} aria-label="Tools">
					<For each={TOOLS}>
						{(tool) => {
							const isActive = () => location.pathname === tool.route;
							return (
								<A
									href={tool.route}
									class={styles.pill}
									classList={{ [styles.pillActive!]: isActive() }}
									style={accentStyle(tool)}
									aria-current={isActive() ? 'page' : undefined}
								>
									{tool.navLabel}
								</A>
							);
						}}
					</For>
				</nav>
			</aside>

			<div class={styles.content}>{props.children}</div>
		</div>
	);
}

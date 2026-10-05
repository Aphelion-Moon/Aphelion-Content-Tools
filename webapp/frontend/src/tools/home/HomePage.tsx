import { For, Show } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { TOOLS } from '~/tools/registry';
import { appState } from '~/store/appStore';
import { formatBytes } from '~/lib/format';
import Elapsed from '~/components/Elapsed';
import styles from './HomePage.module.css';

export default function HomePage() {
	const otherTools = () => TOOLS.filter((tool) => tool.id !== 'home');

	return (
		<div class={styles.dashboard} aria-label="Content tools overview">
			<Card eyebrow="About" heading="Aphelion Content Tools">
				<p>
					A suite of local tools for working on the Meridian-Rift SS13 fork: reviewing and overriding lore
					content, exploring how modules connect to the rest of the checkout, and keeping the game
					repository's Git workflow in one place.
				</p>
				<ul>
					<For each={otherTools()}>
						{(tool) => (
							<li>
								<strong>{tool.navLabel}</strong> — {tool.description}
							</li>
						)}
					</For>
				</ul>
			</Card>

			<Card eyebrow="Shared data store" heading="Database">
				<Show
					when={appState.health}
					fallback={<p class={cardStyles.metadata}>Loading database status…</p>}
				>
					{(health) => (
						<>
							<p>
								<strong>{health().workspace.current ? 'Workspace current' : 'Workspace stale'}</strong>
								<Show when={health().workspace.reason}>
									{(reason) => <> — {reason()}</>}
								</Show>
							</p>
							<ul class={`${cardStyles.metadata} ${styles.metrics}`} aria-label="Workspace datasets">
								<For each={health().workspace.datasets}>
									{(dataset) => (
										<li title={dataset.reason ?? undefined}>
											{dataset.kind}: {dataset.state}
											<Show when={dataset.required}> — required</Show>
										</li>
									)}
								</For>
							</ul>
							<p class={cardStyles.metadata}>
								{health().total_rows.toLocaleString()} rows · {formatBytes(health().disk_bytes)}
								<Show when={health().last_write_time}>
									{(written) => <> · last write <Elapsed since={written()} /> ago</>}
								</Show>
							</p>
							<ul class={`${cardStyles.metadata} ${styles.metrics}`}>
								<For each={Object.entries(health().tables)}>
									{([name, count]) => (
										<li>
											{name}: {count.toLocaleString()}
										</li>
									)}
								</For>
							</ul>
						</>
					)}
				</Show>
			</Card>

			<Card eyebrow="Background jobs" heading="Activity">
				<Show
					when={appState.activeRuns.length > 0}
					fallback={<p class={cardStyles.metadata}>No job is running.</p>}
				>
					<ul class={cardStyles.metadata}>
						<For each={appState.activeRuns}>
							{(run) => (
								<li>
									{run.tool_label ?? run.tool_id} — running for <Elapsed since={run.queued_at} />
								</li>
							)}
						</For>
					</ul>
				</Show>
			</Card>
		</div>
	);
}

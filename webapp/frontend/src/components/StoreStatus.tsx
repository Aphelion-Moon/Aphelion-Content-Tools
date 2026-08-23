import { Show } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { appState } from '~/store/appStore';
import { formatBytes } from '~/lib/format';
import { cx } from '~/lib/cx';
import Elapsed from './Elapsed';
import styles from './StoreStatus.module.css';

/**
 * Glanceable store and job status for the sidebar.
 *
 * Reads entirely from the shared store, which one WebSocket keeps current. Pre-rewrite this widget ran
 * its own 5-second poll against two endpoints, independently on every mounted page.
 */
export default function StoreStatus() {
	const navigate = useNavigate();
	const running = () => appState.activeRuns.length > 0;
	const firstRun = () => appState.activeRuns[0];

	return (
		<div class={styles.wrapper}>
			<button type="button" class={styles.summary} onClick={() => navigate('/file-management')}>
				<Show when={appState.health} fallback={<>Loading database status…</>}>
					{(health) => (
						<>
							{health().total_rows.toLocaleString()} rows · {formatBytes(health().disk_bytes)}
						</>
					)}
				</Show>
			</button>

			<button
				type="button"
				class={cx(styles.pill, running() ? styles.running : styles.idle)}
				onClick={() => navigate('/file-management')}
			>
				<Show when={firstRun()} fallback={<>Idle</>}>
					{(run) => (
						<>
							● {run().tool_label ?? run().tool_id} — <Elapsed since={run().queued_at} />
						</>
					)}
				</Show>
			</button>

			<p class={styles.connection}>
				<span class={cx(styles.dot, appState.connected && styles.dotLive)} />
				{appState.connected ? 'Live' : 'Reconnecting…'}
			</p>
		</div>
	);
}

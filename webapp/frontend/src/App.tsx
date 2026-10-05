import { Router, Route } from '@solidjs/router';
import { For, Suspense, onCleanup, onMount } from 'solid-js';
import AppShell from '~/components/AppShell';
import LoadingIndicator from '~/components/LoadingIndicator';
import { TOOLS } from '~/tools/registry';
import { connectLiveUpdates } from '~/lib/live';
import { startBrowserCompanionRuntime } from '~/lib/parsec/runtime';
import CollaborationStatus from '~/features/collaboration/CollaborationStatus';

export default function App() {
	onMount(() => {
		const disconnectLive = connectLiveUpdates();
		const stopCompanion = startBrowserCompanionRuntime();
		onCleanup(() => {
			disconnectLive();
			stopCompanion();
		});
	});

	return (
		<Router root={(props) => <AppShell><CollaborationStatus />{props.children}</AppShell>}>
			<For each={TOOLS}>
				{(tool) => (
					<Route
						path={tool.route}
						component={() => (
							<Suspense fallback={(
								<LoadingIndicator
									label={`Loading ${tool.navLabel}`}
									tool={tool.id}
									reportThroughParsec
									feedbackKey={`route:${tool.id}`}
								/>
							)}>
								<tool.component />
							</Suspense>
						)}
					/>
				)}
			</For>
			<Route path="*" component={() => <p>That page does not exist.</p>} />
		</Router>
	);
}

import { Router, Route } from '@solidjs/router';
import { For, Suspense, onCleanup, onMount } from 'solid-js';
import AppShell from '~/components/AppShell';
import { TOOLS } from '~/tools/registry';
import { connectLiveUpdates } from '~/lib/live';

export default function App() {
	onMount(() => {
		const disconnect = connectLiveUpdates();
		onCleanup(disconnect);
	});

	return (
		<Router root={(props) => <AppShell>{props.children}</AppShell>}>
			<For each={TOOLS}>
				{(tool) => (
					<Route
						path={tool.route}
						component={() => (
							<Suspense fallback={<p>Loading {tool.navLabel}…</p>}>
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

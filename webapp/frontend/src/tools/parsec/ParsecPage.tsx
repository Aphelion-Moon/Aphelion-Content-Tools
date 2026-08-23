import { For, Show, createSignal } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { appState } from '~/store/appStore';
import { announce, announceError, announceSuccess, react } from '~/lib/notify';
import { formatElapsed } from '~/lib/format';
import { readMotionPreference, writeMotionPreference, type MotionPreference } from '~/lib/parsecEngine';

// Parsec's own page. Her sprite/animation engine is ported in step 4; what works here already is the
// announcement log, which now reads from the shared store rather than a window-global ring buffer -- so
// announcements raised by any tool show up here without the page having been open at the time.
export default function ParsecPage() {
	const [motionPreference, setMotionPreference] = createSignal(readMotionPreference());

	function updateMotionPreference(preference: MotionPreference): void {
		writeMotionPreference(preference);
		setMotionPreference(preference);
	}

	return (
		<>
			<Card eyebrow="Meet the mascot" heading="About Parsec">
				<p>
					Parsec is this app's resident husky. She lives in the sidebar, sits or trots depending on
					whether a background job is running, and delivers a speech bubble whenever something worth
					noticing happens: a save, a commit, an error, a completed refresh.
				</p>
				<p class={cardStyles.metadata}>
					Artwork: cropped and adapted from{' '}
					<a href="https://opengameart.org/content/husky-sprites" target="_blank" rel="noopener">
						"Husky Sprites"
					</a>{' '}
					(OpenGameArt.org), released CC0 / public domain.
				</p>
			</Card>

			<Card eyebrow="Try it out" heading="State preview">
				<p class={cardStyles.metadata}>
					Current state: <strong>{appState.parsecState}</strong>
				</p>
				<label>
					Motion{' '}
					<select
						aria-label="Parsec motion"
						value={motionPreference()}
						onChange={(event) => updateMotionPreference(event.currentTarget.value as MotionPreference)}
					>
						<option value="animate">Animate</option>
						<option value="follow-system">Follow system preference</option>
						<option value="reduce">Reduce motion</option>
					</select>
				</label>
				<button type="button" onClick={() => react('happy')}>
					Happy (pat)
				</button>
				<button type="button" onClick={() => react('twerking', 1800)}>
					Twerking (easter egg)
				</button>
				<button type="button" onClick={() => announceSuccess('Preview success announcement.', 'parsec')}>
					Announce success
				</button>
				<button type="button" onClick={() => announceError(new Error('Preview error announcement.'), 'parsec')}>
					Announce error
				</button>
				<button type="button" onClick={() => announce('Just so you know.', 'info', 'parsec')}>
					Announce info
				</button>
			</Card>

			<Card eyebrow="Log" heading="Recent announcements">
				<Show
					when={appState.announcements.length > 0}
					fallback={<p class={cardStyles.metadata}>Nothing announced yet this session.</p>}
				>
					<ul class={cardStyles.metadata}>
						<For each={appState.announcements}>
							{(entry) => (
								<li>
									[{entry.kind}] {entry.message}
									<Show when={entry.tool}>{(tool) => <> — {tool()}</>}</Show> ·{' '}
									{formatElapsed(entry.at)} ago
								</li>
							)}
						</For>
					</ul>
				</Show>
			</Card>
		</>
	);
}

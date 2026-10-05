import { createSignal } from 'solid-js';
import parsecSpriteUrl from '~/assets/parsec.png';
import Card, { cardStyles } from '~/components/Card';
import { appState } from '~/store/appStore';
import { reactParsec, reportParsec } from '~/lib/parsec/coordinator';
import {
	exportCompanionProfile as serializeCompanionProfile,
	defaultCompanionProfile,
	importCompanionProfile,
	loadCompanionProfile,
	saveCompanionProfile,
	type CompanionProfileV1,
} from '~/lib/parsec/profile';
import type { CompanionSettings } from '~/lib/parsec/companionTypes';
import ActivityHistory from './ActivityHistory';
import styles from './ParsecPage.module.css';

export default function ParsecPage() {
	const [profile, setProfile] = createSignal(loadCompanionProfile());
	const [importStatus, setImportStatus] = createSignal<string | null>(null);

	function persist(next: CompanionProfileV1): void {
		try {
			saveCompanionProfile(window.localStorage, next);
			setProfile(next);
		} catch {
			setImportStatus('Parsec could not save that local setting.');
		}
	}

	function updateSettings(update: (settings: CompanionSettings) => CompanionSettings): void {
		const current = profile();
		persist({ ...current, settings: update(current.settings) });
	}

	function updateAudio(update: Partial<CompanionSettings['audio']>): void {
		updateSettings((settings) => ({ ...settings, audio: { ...settings.audio, ...update } }));
	}

	function downloadProfile(): void {
		const anchor = document.createElement('a');
		anchor.href = `data:application/json;charset=utf-8,${encodeURIComponent(serializeCompanionProfile(profile()))}`;
		anchor.download = 'parsec-companion-profile.json';
		anchor.click();
	}

	async function importProfile(file: File | undefined): Promise<void> {
		if (!file) return;
		const imported = importCompanionProfile(await file.text());
		if (!imported.ok) {
			setImportStatus(imported.error);
			return;
		}
		persist(imported.profile);
		setImportStatus('Profile imported. Parsec remembers these settings in this browser.');
	}

	function returnFurnitureHome(): void {
		const defaults = defaultCompanionProfile();
		persist({
			...profile(),
			furnishings: defaults.furnishings,
		});
		reportParsec({
			type: 'mutation',
			phase: 'completed',
			tool: 'parsec',
			summary: 'Bed and cage returned to the habitat.',
		});
	}

	return (
		<>
			<Card eyebrow="Meet the mascot" heading="About Parsec">
				<p>
					Parsec is this app's resident husky. She lives in her habitat, reports notable work through
					her station-radio log, and only takes excursions after you choose how welcome they are.
				</p>
				<p class={cardStyles.metadata}>
					Artwork: <a href={parsecSpriteUrl}>canonical sprite sheet</a>, regenerated for Parsec and
					 converted to pixel art with <a href="https://portalrabbit.com" target="_blank" rel="noopener">PortalRabbit</a>.
					 Original character reference:{' '}
					<a href="https://opengameart.org/content/husky-sprites" target="_blank" rel="noopener">
						&quot;Husky Sprites&quot;
					</a>{' '}
					(OpenGameArt.org), released CC0 / public domain. Maintainers can find current artwork,
					frame coordinates, and source records in the{' '}
					<a href="/references/parsec-asset-register.md">Parsec asset register</a>.
				</p>
			</Card>

			<Card eyebrow="Try it out" heading="State preview">
				<p class={cardStyles.metadata}>Current state: <strong>{appState.parsecState}</strong></p>
				<div class={styles.actions} role="group" aria-label="Parsec preview actions">
					<button type="button" onClick={() => reactParsec('happy')}>Happy (pat)</button>
					<button type="button" onClick={() => reactParsec('twerking', 1800)}>Twerking (easter egg)</button>
					<button type="button" onClick={() => reportParsec({ type: 'mutation', phase: 'completed', tool: 'parsec', summary: 'Preview mutation completed.' })}>Announce success</button>
					<button type="button" onClick={() => reportParsec({ type: 'job', phase: 'failed', tool: 'parsec', summary: 'Preview job failed.', technicalDetail: 'Preview error announcement.' })}>Announce error</button>
					<button type="button" onClick={() => reportParsec({ type: 'search', phase: 'empty', tool: 'parsec', query: 'preview' })}>Announce info</button>
				</div>
			</Card>

			<Card eyebrow="Where she goes" heading="Presence">
				<div class={styles.settingsGrid}>
					<label>
						Excursion permission
						<select
							aria-label="Parsec excursion consent"
							value={profile().consent}
							onChange={(event) => persist({ ...profile(), consent: event.currentTarget.value as CompanionProfileV1['consent'] })}
						>
							<option value="unconfigured">Ask me after I interact with her</option>
							<option value="allowed">Allow occasional excursions</option>
							<option value="ask-each-time">Ask each time</option>
							<option value="habitat-only">Stay in the habitat</option>
						</select>
					</label>
					<label>
						Roaming behavior
						<select
							aria-label="Parsec presence"
							value={profile().settings.presence}
							onChange={(event) => updateSettings((settings) => ({ ...settings, presence: event.currentTarget.value as CompanionSettings['presence'] }))}
						>
							<option value="habitat-only">Habitat only</option>
							<option value="edge-biased">Edge-biased and nonblocking</option>
							<option value="intrusive">Annoying and intrusive</option>
						</select>
					</label>
				</div>
			</Card>

			<Card eyebrow="How she acts" heading="Personality">
				<div class={styles.settingsGrid}>
					<label>
						Tone
						<select
							aria-label="Parsec personality tone"
							value={profile().settings.personalityTone}
							onChange={(event) => updateSettings((settings) => ({ ...settings, personalityTone: event.currentTarget.value as CompanionSettings['personalityTone'] }))}
						>
							<option value="warm">Warm</option>
							<option value="playful-flirtatious">Playful and lightly flirtatious</option>
							<option value="impish">Impish</option>
						</select>
					</label>
				</div>
			</Card>

			<Card eyebrow="Pick her up" heading="Handling">
				<div class={styles.settingsGrid}>
					<label>
						Grab physics
						<select
							aria-label="Parsec handling physics"
							value={profile().settings.handlingPhysics}
							onChange={(event) => updateSettings((settings) => ({ ...settings, handlingPhysics: event.currentTarget.value as CompanionSettings['handlingPhysics'] }))}
						>
							<option value="carry-only">Carry only</option>
							<option value="gentle-momentum">Gentle momentum</option>
							<option value="full-tossing">Full tossing and bounce</option>
						</select>
					</label>
					<label>
						Reaction intensity
						<select
							aria-label="Parsec handling reactions"
							value={profile().settings.handlingReactions}
							onChange={(event) => updateSettings((settings) => ({ ...settings, handlingReactions: event.currentTarget.value as CompanionSettings['handlingReactions'] }))}
						>
							<option value="subdued">Subdued</option>
							<option value="expressive">Expressive</option>
							<option value="dramatic">Dramatic</option>
						</select>
					</label>
				</div>
			</Card>

			<Card eyebrow="Station radio" heading="Feedback">
				<div class={styles.settingsGrid}>
					<label>
						Chat presentation
						<select aria-label="Parsec chat presentation" value={profile().settings.logMode} onChange={(event) => updateSettings((settings) => ({ ...settings, logMode: event.currentTarget.value as CompanionSettings['logMode'] }))}>
							<option value="compact">Compact live log</option>
							<option value="collapsed">Collapsed indicator</option>
							<option value="expanded">Expanded transcript</option>
						</select>
					</label>
					<label>
						Idle chatter
						<select aria-label="Parsec idle chatter" value={profile().settings.idleChatter} onChange={(event) => updateSettings((settings) => ({ ...settings, idleChatter: event.currentTarget.value as CompanionSettings['idleChatter'] }))}>
							<option value="off">Off</option>
							<option value="rare">Rare</option>
							<option value="occasional">Occasional</option>
							<option value="frequent">Frequent</option>
						</select>
					</label>
					<label class={styles.toggle}>
						<input type="checkbox" checked={profile().settings.feedbackPersonality} onChange={(event) => updateSettings((settings) => ({ ...settings, feedbackPersonality: event.currentTarget.checked }))} />
						Use playful Parsec feedback
					</label>
				</div>
			</Card>

			<Card eyebrow="Barks and station noises" heading="Audio">
				<div class={styles.settingsGrid}>
					<label class={styles.toggle}>
						<input aria-label="Parsec audio enabled" type="checkbox" checked={profile().settings.audio.enabled} onChange={(event) => updateAudio({ enabled: event.currentTarget.checked })} />
						Audio enabled after browser unlock
					</label>
					{([
						['master', 'Master', 'Parsec master volume'],
						['voice', 'Voice', 'Parsec voice volume'],
						['effects', 'Effects', 'Parsec effects volume'],
						['alerts', 'Alerts', 'Parsec alert volume'],
						['rareIdle', 'Rare idle sounds', 'Parsec rare idle volume'],
					] as const).map(([key, label, ariaLabel]) => (
						<label>
							{label}: {Math.round(profile().settings.audio[key] * 100)}%
							<input type="range" aria-label={ariaLabel} min="0" max="1" step="0.05" value={profile().settings.audio[key]} onInput={(event) => updateAudio({ [key]: Number(event.currentTarget.value) })} />
						</label>
					))}
				</div>
			</Card>

			<Card eyebrow="Comfort and focus" heading="Accessibility">
				<div class={styles.settingsGrid}>
					<label>
						Motion
						<select aria-label="Parsec motion" value={profile().settings.motion} onChange={(event) => updateSettings((settings) => ({ ...settings, motion: event.currentTarget.value as CompanionSettings['motion'] }))}>
							<option value="animate">Animate</option>
							<option value="reduce">Reduce motion</option>
						</select>
					</label>
					<label class={styles.toggle}>
						<input aria-label="Parsec reduced distraction" type="checkbox" checked={profile().settings.reducedDistraction} onChange={(event) => updateSettings((settings) => ({ ...settings, reducedDistraction: event.currentTarget.checked }))} />
						Suppress autonomous behavior while focusing
					</label>
				</div>
			</Card>

			<Card eyebrow="Local profile" heading="Companion data">
				<p class={cardStyles.metadata}>Profile import/export contains Parsec settings and familiarity only. It does not contain or fabricate activity history.</p>
				<div class={styles.actions}>
					<button type="button" aria-label="Export companion profile" onClick={downloadProfile}>Export companion profile</button>
					<button type="button" aria-label="Return Parsec furniture home" onClick={returnFurnitureHome}>Return bed and cage home</button>
					<label class={styles.fileButton}>
						Import companion profile
						<input aria-label="Import companion profile" type="file" accept="application/json,.json" onChange={(event) => void importProfile(event.currentTarget.files?.[0])} />
					</label>
				</div>
				{importStatus() && <p role="status">{importStatus()}</p>}
			</Card>

			<ActivityHistory />
		</>
	);
}

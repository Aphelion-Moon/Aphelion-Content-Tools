import { For, Show, createResource, createSignal } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { ApiError, api } from '~/lib/api';
import { announceError, announceSuccess } from '~/lib/notify';
import type { components } from '~/lib/api-schema';
import styles from './FileManagement.module.css';

type ExportStagesResponse = components['schemas']['ExportStagesResponse'];
type PrepareExportResponse = components['schemas']['PrepareExportResponse'];
type ApplyExportResponse = components['schemas']['ApplyExportResponse'];

export default function ExportPanel() {
	const [output, setOutput] = createSignal('');
	const [busy, setBusy] = createSignal(false);
	const [chosenStage, setChosenStage] = createSignal('');

	const [stages, { refetch }] = createResource(() => api.get<ExportStagesResponse>('/api/export/stages'));

	// Stage names are UTC timestamps ("YYYYMMDDThhmmssZ-<hash>") returned in ascending order, so the last
	// entry is always the newest -- the picker defaults to it rather than to a stale prior selection.
	const latestStage = () => {
		const list = stages()?.stages ?? [];
		return list.length ? list[list.length - 1]!.stage : '';
	};
	const selected = () => chosenStage() || latestStage();

	async function prepare(): Promise<void> {
		setBusy(true);
		setOutput('Preparing export…');
		try {
			const result = await api.post<PrepareExportResponse>('/api/export/prepare');
			setOutput(
				`Prepared stage ${result.stage}. Review the manifest below, then Apply to write it into ` +
					`Meridian-Rift.\n\n${JSON.stringify(result.manifest, null, 2)}`,
			);
			announceSuccess(`Prepared export stage ${result.stage}.`, 'file-management');
			setChosenStage('');
			await refetch();
		} catch (error) {
			setOutput(error instanceof Error ? error.message : String(error));
			announceError(error, 'file-management');
		} finally {
			setBusy(false);
		}
	}

	async function apply(force = false): Promise<void> {
		const stage = selected();
		if (!stage) {
			setOutput('Prepare an export before applying one.');
			return;
		}
		setBusy(true);
		setOutput('Applying export…');
		try {
			const result = await api.post<ApplyExportResponse>('/api/export/apply', { stage, force });
			const desktopNote = result.opened_in_github_desktop
				? 'GitHub Desktop opened for the game checkout.'
				: `Could not open GitHub Desktop${result.github_desktop_error ? `: ${result.github_desktop_error}` : '.'} ` +
					'Open it manually to review, commit, and open a pull request.';
			setOutput(
				`Applied ${result.artifact}${force ? ' (overrode the uncommitted-changes check)' : ''}.\n` +
					`Review the game diff under Meridian-Rift, then commit it locally.\n${desktopNote}`,
			);
			announceSuccess(`Applied ${result.artifact}.`, 'file-management');
		} catch (error) {
			// A dirty game checkout is a deliberate stop condition, not a failure to paper over -- offer
			// the override explicitly rather than retrying with force automatically.
			const message = error instanceof ApiError ? error.message : String(error);
			if (!force && /uncommitted changes/i.test(message)) {
				const proceed = window.confirm(
					'Meridian-Rift has uncommitted changes.\n\n' +
						'Apply the export anyway? This only overwrites the generated lore artifact — your other ' +
						'uncommitted changes are left alone, but review them before committing.',
				);
				if (proceed) {
					setBusy(false);
					return apply(true);
				}
			}
			setOutput(message);
			announceError(error, 'file-management');
		} finally {
			setBusy(false);
		}
	}

	return (
		<Card eyebrow="Repository operations" heading="Stage a Commit">
			<p class={cardStyles.metadata}>
				Writes the generated lore override artifact into the game checkout. Three steps, always in order:{' '}
				<strong>generate</strong> builds and validates the artifact outside the checkout and is always safe
				to run; <strong>select</strong> the stage to apply, defaulting to the newest; then{' '}
				<strong>apply</strong> writes it in and opens GitHub Desktop so you can review the diff.
			</p>

			<div class={styles.group}>
				<h3>1. Generate a new stage</h3>
				<div class={styles.toolList}>
					<button type="button" disabled={busy()} onClick={() => void prepare()}>
						Prepare stage
					</button>
				</div>
			</div>

			<div class={styles.group}>
				<h3>2. Select a stage to apply</h3>
				<Show
					when={(stages()?.stages ?? []).length > 0}
					fallback={<p class={cardStyles.metadata}>No prepared stages — prepare one first.</p>}
				>
					<select
						aria-label="Stage to apply"
						value={selected()}
						onChange={(event) => setChosenStage(event.currentTarget.value)}
					>
						<For each={stages()?.stages ?? []}>
							{(stage) => {
								const overrides = (stage.manifest as { entry_ids?: unknown[] }).entry_ids?.length ?? 0;
								return (
									<option value={stage.stage}>
										{stage.stage} · {overrides} override(s)
									</option>
								);
							}}
						</For>
					</select>
				</Show>
			</div>

			<div class={styles.group}>
				<h3>3. Apply selected stage</h3>
				<div class={styles.toolList}>
					<button type="button" disabled={busy() || !selected()} onClick={() => void apply()}>
						Apply stage
					</button>
				</div>
			</div>

			<Show when={output()}>
				{(text) => (
					<pre class={styles.output} aria-live="polite">
						{text()}
					</pre>
				)}
			</Show>
		</Card>
	);
}

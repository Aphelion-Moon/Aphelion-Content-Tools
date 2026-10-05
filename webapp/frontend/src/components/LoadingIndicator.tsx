import { onCleanup, onMount } from 'solid-js';
import { reportParsec } from '~/lib/parsec/coordinator';
import styles from './LoadingIndicator.module.css';

export default function LoadingIndicator(props: {
	readonly label: string;
	readonly tool?: string | null;
	readonly announceThroughParsec?: boolean;
	readonly reportThroughParsec?: boolean;
	readonly feedbackKey?: string;
}) {
	onMount(() => {
		if (!(props.reportThroughParsec || props.announceThroughParsec)) return;
		const dedupeKey = props.feedbackKey ?? `loading:${props.tool ?? 'app'}:${props.label}`;
		reportParsec({
			type: 'fetch',
			phase: 'started',
			tool: props.tool ?? null,
			summary: props.label,
			dedupeKey,
		});
		onCleanup(() => {
			reportParsec({
				type: 'fetch',
				phase: 'completed',
				tool: props.tool ?? null,
				summary: props.label.replace(/^Loading\s+/i, 'Loaded '),
				dedupeKey,
			});
		});
	});

	return (
		<div class={styles.indicator} role="status" aria-live="polite">
			<span>{props.label}</span>
			<div
				class={styles.track}
				role="progressbar"
				aria-label={props.label}
				aria-valuetext={props.label}
			>
				<span class={styles.bar} />
			</div>
		</div>
	);
}

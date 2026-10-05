import { For, Show } from 'solid-js';
import { appState } from '~/store/appStore';
import type { ParsecLogMode } from '~/lib/parsec/types';
import styles from './ParsecRadioLog.module.css';

export interface ParsecRadioLogProps {
	readonly mode?: ParsecLogMode;
}

const COMPACT_LINE_LIMIT = 5;

function timestamp(at: number): string {
	return new Date(at * 1_000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function ParsecRadioLog(props: ParsecRadioLogProps) {
	const mode = () => props.mode ?? 'compact';
	const lines = () => mode() === 'expanded'
		? appState.parsecLog
		: appState.parsecLog.slice(0, COMPACT_LINE_LIMIT);
	const newestIsError = () => appState.parsecLog[0]?.kind === 'error';
	const expanded = () => mode() === 'expanded' || newestIsError();

	return (
		<section
			class={styles.log}
			data-parsec-radio-log
			data-mode={mode()}
			data-expanded={expanded() ? 'true' : 'false'}
			aria-label="Parsec radio"
		>
			<header class={styles.header}>
				<span class={styles.channel}>[Companion]</span>
				<span class={styles.signal} aria-hidden="true">●</span>
				<span class={styles.title}>Parsec radio</span>
			</header>
			<Show
				when={mode() !== 'collapsed'}
				fallback={(
					<a class={styles.collapsed} href="/parsec#activity-history">
						{appState.parsecLog.filter((line) => line.unread).length} unread — open activity history
					</a>
				)}
			>
				<Show
					when={lines().length > 0}
					fallback={<p class={styles.quiet}><span class={styles.speaker}>Parsec:</span> Radio quiet. *wuffs softly.*</p>}
				>
					<ol class={styles.lines}>
						<For each={lines()}>
							{(line, index) => {
								const isNewest = () => index() === 0;
								return (
									<li
										class={styles[line.kind]}
										data-unread={line.unread ? 'true' : 'false'}
									>
										<div
											class={styles.message}
											data-parsec-copy
											role={isNewest() ? (line.kind === 'error' ? 'alert' : 'status') : undefined}
											aria-live={isNewest() ? (line.kind === 'error' ? 'assertive' : 'polite') : undefined}
										>
											<time dateTime={new Date(line.at * 1_000).toISOString()}>{timestamp(line.at)}</time>
											<span class={styles.speaker}>Parsec:</span>
											<span>{line.message}</span>
										</div>
										<Show when={line.technicalDetail}>
											<a class={styles.detailsLink} href={`/parsec#activity-${encodeURIComponent(line.activityId)}`}>
												View technical details in activity history
											</a>
										</Show>
									</li>
								);
							}}
						</For>
					</ol>
				</Show>
			</Show>
		</section>
	);
}

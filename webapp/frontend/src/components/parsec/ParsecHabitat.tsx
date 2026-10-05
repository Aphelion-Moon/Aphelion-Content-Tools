import { createSignal, type JSX } from 'solid-js';
import { cx } from '~/lib/cx';
import styles from './ParsecHabitat.module.css';

interface ParsecHabitatProps {
	readonly children: JSX.Element;
}

export default function ParsecHabitat(props: ParsecHabitatProps) {
	const [expanded, setExpanded] = createSignal(false);
	let surfaceRef: HTMLDivElement | undefined;

	function toggle(): void {
		setExpanded((current) => !current);
		queueMicrotask(() => surfaceRef?.focus());
	}

	return (
		<section
			class={styles.habitat}
			data-parsec-habitat
			data-expanded={expanded() ? 'true' : 'false'}
			aria-label="Parsec habitat"
		>
			<div
				ref={surfaceRef}
				class={cx(styles.surface, expanded() && styles.expanded)}
				data-parsec-habitat-surface
				tabIndex={-1}
				onKeyDown={(event) => {
					if (event.key !== 'Escape' || !expanded()) return;
					event.preventDefault();
					setExpanded(false);
				}}
			>
				<button
					type="button"
					class={styles.expandControl}
					aria-label={expanded() ? 'Close Parsec habitat' : 'Expand Parsec habitat'}
					aria-expanded={expanded()}
					onClick={toggle}
				>
					{expanded() ? 'Close' : 'Expand'}
				</button>
				{props.children}
			</div>
		</section>
	);
}

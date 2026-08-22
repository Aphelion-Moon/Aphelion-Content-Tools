import { Show, type JSX } from 'solid-js';
import styles from './Card.module.css';

interface CardProps {
	readonly eyebrow?: string;
	readonly heading?: string;
	readonly children?: JSX.Element;
}

export default function Card(props: CardProps) {
	return (
		<section class={styles.card}>
			<Show when={props.eyebrow}>{(text) => <p class={styles.eyebrow}>{text()}</p>}</Show>
			<Show when={props.heading}>{(text) => <h2 class={styles.heading}>{text()}</h2>}</Show>
			{props.children}
		</section>
	);
}

export { styles as cardStyles };

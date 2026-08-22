import Card, { cardStyles } from '~/components/Card';

// Placeholder. Ported in step 4 of the rewrite; the legacy page at /graph remains authoritative until
// then. The port keeps graphology/Sigma.js/d3-force and mounts them onto a ref in onMount -- they are
// rendering engines independent of any UI framework -- and moves graph.css's page-specific overrides into
// a scoped module so its bare `button { width: auto }` rule stops leaking to every other tool.
export default function ContentGraphPage() {
	return (
		<Card eyebrow="Modular content" heading="Content Graph">
			<p class={cardStyles.metadata}>Not yet ported to the new shell.</p>
		</Card>
	);
}

import Card, { cardStyles } from '~/components/Card';

// Placeholder. Ported in step 4 of the rewrite; the legacy page at /lore-editor remains authoritative
// until then. This is the port that adopts TanStack Virtual and removes the 500-row cap.
export default function LoreEditorPage() {
	return (
		<Card eyebrow="Catalog" heading="Lore Editor">
			<p class={cardStyles.metadata}>Not yet ported to the new shell.</p>
		</Card>
	);
}

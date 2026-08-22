import Card, { cardStyles } from '~/components/Card';

// Placeholder. Ported in step 4 of the rewrite; the legacy page at /file-management remains authoritative
// until then.
export default function FileManagementPage() {
	return (
		<Card eyebrow="Repository operations" heading="File Management">
			<p class={cardStyles.metadata}>Not yet ported to the new shell.</p>
		</Card>
	);
}

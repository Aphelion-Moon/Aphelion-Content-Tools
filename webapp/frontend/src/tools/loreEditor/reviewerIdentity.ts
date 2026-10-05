const REVIEWER_IDENTITY_KEY = 'aphelion-lore-reviewer';

export function readReviewerIdentity(): string {
	try {
		return window.localStorage.getItem(REVIEWER_IDENTITY_KEY)?.trim() ?? '';
	} catch {
		return '';
	}
}

export function writeReviewerIdentity(value: string): void {
	try {
		const reviewer = value.trim();
		if (reviewer) window.localStorage.setItem(REVIEWER_IDENTITY_KEY, reviewer);
		else window.localStorage.removeItem(REVIEWER_IDENTITY_KEY);
	} catch {
		// Browser privacy settings may disable storage; the in-memory identity remains usable.
	}
}

/** Guards asynchronous UI work against superseded requests and disposed owners.
 * Capture before awaiting; check before updating state, reporting feedback, or scheduling more work.
 * This is independent of Solid so any tool or shared service can own the same lifecycle contract.
 */
export function createAsyncScope() {
	let generation = 0;
	let disposed = false;
	return {
		capture(): () => boolean {
			const captured = generation;
			return () => !disposed && generation === captured;
		},
		invalidate(): void { generation += 1; },
		dispose(): void { disposed = true; generation += 1; },
	};
}

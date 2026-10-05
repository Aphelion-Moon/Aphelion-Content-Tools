import type { RandomSource } from './companionScheduler';
import type { Point, Rect } from './geometry';

export interface SafeRegionSnapshot {
	viewport: Rect;
	shellChrome: Rect[];
	interactiveControls: Rect[];
	selectionRanges: Rect[];
}

function rectFromDom(rect: Pick<DOMRect, 'x' | 'y' | 'width' | 'height'>): Rect {
	return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
}

function visibleRects(elements: Iterable<Element>): Rect[] {
	const result: Rect[] = [];
	for (const element of elements) {
		const rect = element.getBoundingClientRect();
		if (rect.width > 0 && rect.height > 0) result.push(rectFromDom(rect));
	}
	return result;
}

export function collectSafeRegions(
	root: ParentNode,
	viewportSize: { width: number; height: number } = { width: window.innerWidth, height: window.innerHeight },
): SafeRegionSnapshot {
	const selectionRanges: Rect[] = [];
	const selection = typeof window.getSelection === 'function' ? window.getSelection() : null;
	if (selection) {
		for (let index = 0; index < selection.rangeCount; index += 1) {
			for (const rect of selection.getRangeAt(index).getClientRects()) {
				if (rect.width > 0 && rect.height > 0) selectionRanges.push(rectFromDom(rect));
			}
		}
	}
	return {
		viewport: { x: 0, y: 0, width: viewportSize.width, height: viewportSize.height },
		shellChrome: visibleRects(root.querySelectorAll('[data-shell-chrome]')),
		interactiveControls: visibleRects(root.querySelectorAll('button, a[href], input, select, textarea, [contenteditable="true"], [role="button"]')),
		selectionRanges,
	};
}

function intersects(left: Rect, right: Rect): boolean {
	return left.x < right.x + right.width
		&& left.x + left.width > right.x
		&& left.y < right.y + right.height
		&& left.y + left.height > right.y;
}

function actorRect(point: Point, size: { width: number; height: number }): Rect {
	return { ...point, ...size };
}

export function chooseOrdinaryPerch(
	snapshot: SafeRegionSnapshot,
	actorSize: { width: number; height: number },
	random: RandomSource,
): Point | null {
	const margin = 12;
	const { viewport } = snapshot;
	const maximumX = viewport.x + Math.max(0, viewport.width - actorSize.width);
	const maximumY = viewport.y + Math.max(0, viewport.height - actorSize.height);
	const middleX = viewport.x + Math.max(0, (viewport.width - actorSize.width) / 2);
	const middleY = viewport.y + Math.max(0, (viewport.height - actorSize.height) / 2);
	const candidates: Point[] = [
		{ x: middleX, y: viewport.y + margin },
		{ x: maximumX - margin, y: middleY },
		{ x: middleX, y: maximumY - margin },
		{ x: viewport.x + margin, y: middleY },
		{ x: viewport.x + margin, y: viewport.y + margin },
		{ x: maximumX - margin, y: viewport.y + margin },
		{ x: maximumX - margin, y: maximumY - margin },
		{ x: viewport.x + margin, y: maximumY - margin },
	];
	const blocked = [...snapshot.shellChrome, ...snapshot.interactiveControls, ...snapshot.selectionRanges];
	const start = Math.floor(Math.min(0.999999, Math.max(0, random.next())) * candidates.length);
	for (let offset = 0; offset < candidates.length; offset += 1) {
		const candidate = candidates[(start + offset) % candidates.length]!;
		if (!blocked.some((rect) => intersects(actorRect(candidate, actorSize), rect))) return candidate;
	}
	return null;
}

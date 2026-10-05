export interface Point {
	x: number;
	y: number;
}

export interface Rect extends Point {
	width: number;
	height: number;
}

export function clampPoint(point: Point, bounds: Rect): Point {
	return {
		x: Math.min(bounds.x + Math.max(0, bounds.width), Math.max(bounds.x, point.x)),
		y: Math.min(bounds.y + Math.max(0, bounds.height), Math.max(bounds.y, point.y)),
	};
}

export function normalizePoint(point: Point, bounds: Rect): Point {
	if (bounds.width <= 0 || bounds.height <= 0) return { x: 0, y: 0 };
	const clamped = clampPoint(point, bounds);
	return {
		x: (clamped.x - bounds.x) / bounds.width,
		y: (clamped.y - bounds.y) / bounds.height,
	};
}

export function denormalizePoint(point: Point, bounds: Rect): Point {
	return clampPoint({
		x: bounds.x + Math.min(1, Math.max(0, point.x)) * Math.max(0, bounds.width),
		y: bounds.y + Math.min(1, Math.max(0, point.y)) * Math.max(0, bounds.height),
	}, bounds);
}

export function pointInRect(point: Point, bounds: Rect): boolean {
	return point.x >= bounds.x
		&& point.x <= bounds.x + Math.max(0, bounds.width)
		&& point.y >= bounds.y
		&& point.y <= bounds.y + Math.max(0, bounds.height);
}

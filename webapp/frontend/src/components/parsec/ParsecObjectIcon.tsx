import { Show } from 'solid-js';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import styles from './ParsecObjectIcon.module.css';

export const PARSEC_TOOL_OBJECTS: Readonly<Partial<Record<string, string>>> = {
	ball: 'tennis-ball', tug: 'tug-rope', brush: 'hairbrush', bed: 'dogbed', cage: 'cage-open',
};

// Small flat pixel glyphs for actions without a physical object in the atlas.
const TOOL_GLYPHS: Readonly<Record<string, { path: string; color: string }>> = {
	pat: { path: 'M3 3h2v3H3z M7 2h2v3H7z M11 3h2v3h-2z M1 7h2v3H1z M13 7h2v3h-2z M6 7h4v2h2v4h-2v1H6v-1H4V9h2z', color: '#FF3CC8' },
	treat: { path: 'M2 4h3v2h6V4h3v3h-1v2h1v3h-3v-2H5v2H2V9h1V7H2z', color: '#E8D7A1' },
	whistle: { path: 'M2 6h7V4h5v3h-4v5H8v1H4v-1H2z M4 4h3v1H4z', color: '#50DCEB' },
};

/** Decorative atlas art; the owning control retains its visible and accessible label. */
export default function ParsecObjectIcon(props: { objectId?: string | undefined; tool?: string; size?: number }) {
	const frame = () => {
		const id = props.objectId && coreFallbackManifest.objects[props.objectId]?.frameId;
		return id ? coreFallbackManifest.frames[id] : undefined;
	};
	const sheet = () => frame() && coreFallbackManifest.sheets[frame()!.sheetId];
	const scale = () => (props.size ?? 32) / Math.max(frame()!.width, frame()!.height);
	const glyph = () => props.tool ? TOOL_GLYPHS[props.tool] : undefined;
	return <Show when={frame() && sheet()} fallback={
		<Show when={glyph()} keyed>{(shape) => (
			<svg class={styles.icon} data-parsec-tool-icon={props.tool} aria-hidden="true"
				viewBox="0 0 16 16" width={props.size ?? 32} height={props.size ?? 32} shape-rendering="crispEdges">
				<path d={shape.path} fill={shape.color} stroke="#202129" stroke-width="1" stroke-linejoin="miter" />
			</svg>
		)}</Show>
	}>
		<span class={styles.icon} data-parsec-object-icon={props.objectId} aria-hidden="true" style={{
			width: `${frame()!.width * scale()}px`,
			height: `${frame()!.height * scale()}px`,
			'background-image': `url(${sheet()!.src})`,
			'background-position': `-${frame()!.x * scale()}px -${frame()!.y * scale()}px`,
			'background-size': `${sheet()!.width * scale()}px ${sheet()!.height * scale()}px`,
		}} />
	</Show>;
}

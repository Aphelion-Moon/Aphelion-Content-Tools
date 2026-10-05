import { For, Show } from 'solid-js';
import ParsecObjectIcon, { PARSEC_TOOL_OBJECTS } from './ParsecObjectIcon';
import styles from './ParsecToolbar.module.css';

export type ParsecToolId = 'pat' | 'ball' | 'tug' | 'brush' | 'treat' | 'whistle' | 'bed' | 'cage';

interface ParsecToolbarProps {
	readonly onTool: (tool: ParsecToolId, trigger?: HTMLButtonElement) => void;
	readonly cageLatched: boolean;
	readonly activeTool?: ParsecToolId | null;
}

const TOOLS: ReadonlyArray<{
	id: Exclude<ParsecToolId, 'cage'>;
	label: string;
	ariaLabel: string;
	description: string;
}> = [
	{ id: 'pat', label: 'Pat', ariaLabel: 'Pat Parsec', description: 'Give Parsec a pat or boop.' },
	{ id: 'ball', label: 'Ball', ariaLabel: 'Throw ball', description: 'Place or throw her ball.' },
	{ id: 'tug', label: 'Tug', ariaLabel: 'Play tug', description: 'Start a tug game.' },
	{ id: 'brush', label: 'Brush', ariaLabel: 'Brush Parsec', description: 'Brush her coat.' },
	{ id: 'treat', label: 'Treat', ariaLabel: 'Offer treat', description: 'Offer a treat with no care meter.' },
	{ id: 'whistle', label: 'Whistle', ariaLabel: 'Whistle', description: 'Recall or invite Parsec.' },
	{ id: 'bed', label: 'Bed', ariaLabel: 'Go to bed', description: 'Send Parsec to her bed.' },
];

export default function ParsecToolbar(props: ParsecToolbarProps) {
	return (
		<div class={styles.toolbar} role="toolbar" aria-label="Parsec toys and interactions" data-parsec-toolbar>
			<For each={TOOLS}>
				{(tool) => (
					<button
						type="button"
						class={styles.tool}
						aria-label={tool.ariaLabel}
						disabled={props.cageLatched}
						aria-pressed={['ball', 'tug', 'brush', 'treat'].includes(tool.id) ? props.activeTool === tool.id : undefined}
						title={tool.description}
						onClick={(event) => props.onTool(tool.id, event.currentTarget)}
					>
						<ParsecObjectIcon objectId={PARSEC_TOOL_OBJECTS[tool.id]} tool={tool.id} />
						{tool.label}
					</button>
				)}
			</For>
			<button
				type="button"
				class={styles.tool}
				aria-label={props.cageLatched ? 'Release Parsec' : 'Go to cage'}
				title={props.cageLatched ? 'Open the cage and release Parsec.' : 'Send Parsec into her cage.'}
				onClick={(event) => props.onTool('cage', event.currentTarget)}
			>
				<ParsecObjectIcon objectId={props.cageLatched ? 'cage-locked' : 'cage-open'} />
				{props.cageLatched ? 'Release' : 'Cage'}
			</button>
			<Show when={props.cageLatched}><p class={styles.hint}>Release Parsec to use toys and interactions.</p></Show>
		</div>
	);
}

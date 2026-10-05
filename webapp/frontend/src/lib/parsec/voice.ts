import type { ParsecEvent, ParsecFeedbackDraft } from './types';
import type { CompanionDialogueLineId } from './companionTypes';

const COMPANION_LINES: Record<CompanionDialogueLineId, string> = {
	'handling.warm.subdued.slow.new': '*wuffs softly.* Easy there. I’m coming with you.',
	'handling.playful.expressive.slow.new': '*squirms playfully.* A lift? Don’t mind if I do.',
	'handling.playful.expressive.fast.familiar': '*wags midair.* You know I like the scenic route.',
	'handling.playful.dramatic.fast.familiar': '*kicks her paws playfully.* Airborne again! Stick the landing, human.',
	'handling.impish.dramatic.fast.familiar': '*squirms with an impish grin.* Your cargo has opinions about this route.',
	'furniture.bed.timeout': '*huffs and curls up.* Fine. I’ll think about it from my bed.',
	'furniture.bed.voluntary': '*yawns and pads to her bed.* Patrol break. Save me a good story.',
	'furniture.cage.enter': '*sniffs the doorway.* Checking out my little station nook.',
	'furniture.cage.closed': '*settles with a theatrical huff.* I’ll supervise from here, then.',
	'furniture.cage.released': '*wags and steps out.* Back on patrol!',
};

const IDLE_LINES: Readonly<Record<string, readonly string[]>> = {
	'/': [
		'*wuffs softly.* All quiet on the station. Even Cargo looks innocent.',
		'*sniffs the air.* No plasma fires nearby. Probably.',
		'*wags her tail.* The arrivals shuttle has not hit anything important.',
	],
	'/lore-editor': [
		'*sniffs around the review queue.* No stale lore scents yet.',
		'*snuffles through the filing cabinet.* Every record is still where we left it.',
		'*wuffs softly.* The library is quiet; no rogue bookworms on sensors.',
	],
	'/graph': [
		'*tilts her head at the node map.* All those little station trails connect somewhere.',
		'*sniffs along the graph edges.* No orphaned scent trails in this sector.',
		'*wuffs softly.* The attribution lattice is holding steady.',
	],
	'/file-management': [
		'*stares at the repository console.* The commit button remains human-operated.',
		'*snuffles around the staging area.* No loose artifacts under the grilles.',
		'*wuffs softly.* Git status is a better detective than Security today.',
	],
	'/parsec': [
		'*wags her tail excitedly!* Mascot diagnostics nominal.',
		'*stops running for a moment and pants heavily.* Patrol break acquired.',
		'*licks your nose.* Parsec calibration complete.',
	],
};

const FALLBACK_IDLE_LINES = [
	'*wuffs softly.* All quiet on the station.',
	'*sniffs the corridor.* Nothing urgent on this deck.',
	'*snuffles.* Station patrol continues.',
] as const;

function draft(
	event: ParsecEvent,
	text: string,
	kind: ParsecFeedbackDraft['kind'],
	animation: ParsecFeedbackDraft['animation'],
): ParsecFeedbackDraft {
	return {
		text,
		kind,
		animation,
		tool: event.tool,
		technicalDetail: event.technicalDetail ?? null,
		dedupeKey: event.dedupeKey ?? null,
	};
}

export function voiceForEvent(event: ParsecEvent): ParsecFeedbackDraft {
	switch (event.type) {
		case 'search':
			switch (event.phase) {
				case 'started':
					return draft(event, '*sniffs.* Digging through the selected context…', 'info', 'search');
				case 'completed': {
					const count = event.resultCount ?? 0;
					const records = count === 1 ? 'record' : 'records';
					return draft(event, `*wags her tail excitedly!* I dug up ${count} matching ${records}.`, 'success', 'happy');
				}
				case 'empty':
					return draft(event, '*tilts her head in confusion.* No matching records in this context.', 'info', 'confused');
				case 'failed':
					return draft(event, '*growls in frustration.* Search failed; the exact error is in the results panel.', 'error', 'growl');
				case 'superseded':
					return draft(event, '*snuffles.* New scent picked up; switching searches.', 'info', 'search');
			}
		case 'fetch':
			switch (event.phase) {
				case 'started':
					return draft(event, `*sniffs.* ${event.summary}`, 'info', 'fetch');
				case 'delayed':
					return draft(event, `*snuffles around the catalog.* Still fetching! ${event.summary}`, 'info', 'fetch');
				case 'completed':
					return draft(event, `*wuffs softly.* ${event.summary}`, 'success', 'happy');
				case 'failed':
					return draft(event, `*growls angrily at the code.* ${event.summary}`, 'error', 'growl');
				case 'cancelled':
					return draft(event, `*wuffs softly.* ${event.summary}`, 'info', 'idle');
			}
		case 'mutation':
			return event.phase === 'completed'
				? draft(event, `*wags her tail excitedly!* ${event.summary}`, 'success', 'happy')
				: draft(event, `*growls angrily at the code.* ${event.summary}`, 'error', 'growl');
		case 'job':
			switch (event.phase) {
				case 'started':
					return draft(event, `*heckin' BORKS.* ${event.summary}`, 'info', 'working');
				case 'progress':
					return draft(event, `*snuffles busily.* ${event.summary}`, 'info', 'working');
				case 'completed':
					return draft(event, `*woofs.* ${event.summary}`, 'success', 'happy');
				case 'failed':
					return draft(event, `*growls angrily at the code.* ${event.summary}`, 'error', 'growl');
			}
		case 'connection':
			switch (event.phase) {
				case 'connected':
					return draft(event, '*wuffs softly.* Live station link connected.', 'success', 'happy');
				case 'disconnected':
					return draft(event, '*whines anxiously…* I lost the live station link.', 'error', 'anxious');
				case 'polling':
					return draft(event, '*sniffs for a backup route.* Using station polling for now.', 'warning', 'search');
				case 'recovered':
					return draft(event, '*wags her tail excitedly!* Live station link recovered.', 'success', 'happy');
			}
		case 'validation':
			switch (event.phase) {
				case 'warning':
					return draft(event, `*wuffs softly.* ${event.summary}`, 'warning', 'anxious');
				case 'blocked':
					return draft(event, `*stares disapprovingly.* ${event.summary}`, 'warning', 'anxious');
				case 'failed':
					return draft(event, `*growls in frustration.* ${event.summary}`, 'error', 'growl');
			}
		case 'navigation':
			return draft(event, `*sniffs.* New station deck: ${event.route}.`, 'info', 'idle');
		case 'interaction':
			if (event.phase === 'companion') return draft(event, COMPANION_LINES[event.lineId], 'info', 'idle');
			return event.phase === 'repeated-pat'
				? draft(event, '*twerks in her boredom.* You found the secret reaction.', 'info', 'twerking')
				: draft(event, '*licks your hand.* Good human.', 'info', 'happy');
		case 'idle': {
			const lines = IDLE_LINES[event.route] ?? FALLBACK_IDLE_LINES;
			const lineIndex = Math.max(0, event.lineIndex ?? 0) % lines.length;
			const line = lines[lineIndex]!;
			return draft(event, line, 'info', 'idle');
		}
		case 'notice':
			switch (event.phase) {
				case 'info':
					return draft(event, `*wuffs softly.* ${event.summary}`, 'info', 'idle');
				case 'success':
					return draft(event, `*wags her tail excitedly!* ${event.summary}`, 'success', 'happy');
				case 'error':
					return draft(event, `*growls in frustration.* ${event.summary}`, 'error', 'growl');
			}
	}
}

import type { CollaborationVersion } from './api';

export interface CollaborationState {
	readonly phase: 'checking' | 'unavailable' | 'incompatible' | 'restricted';
	readonly message: string;
	readonly version?: CollaborationVersion;
}

export function versionState(version: CollaborationVersion, authorizationReason: string): CollaborationState {
	return version.compatible
		? { phase: 'restricted', message: `Compatible — ${authorizationReason}`, version }
		: { phase: 'incompatible', message: 'Incompatible', version };
}

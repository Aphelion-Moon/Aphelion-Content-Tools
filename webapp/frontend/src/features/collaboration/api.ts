import type { components } from '~/lib/api-schema';
import { api } from '~/lib/api';

export type CollaborationVersion = components['schemas']['CollaborationVersionResponse'];
export type CollaborationCapabilities = components['schemas']['CollaborationCapabilitiesResponse'];

export const collaborationApi = {
	capabilities: () => api.get<CollaborationCapabilities>('/api/collaboration/capabilities'),
	version: () => api.get<CollaborationVersion>('/api/collaboration/version'),
};

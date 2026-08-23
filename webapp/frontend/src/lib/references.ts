import { createSignal } from 'solid-js';
import { api } from './api';
import type { components } from './api-schema';

export type Reference = components['schemas']['Reference'];
export type AddReferenceRequest = components['schemas']['AddReferenceRequest'];
export type ReferenceListResponse = components['schemas']['ReferenceListResponse'];

const [revision, setRevision] = createSignal(0);

export function referenceRevision(): number {
	return revision();
}

export async function listReferences(): Promise<ReferenceListResponse> {
	return api.get<ReferenceListResponse>('/api/references');
}

export async function addReference(payload: AddReferenceRequest): Promise<Reference> {
	const created = await api.post<Reference>('/api/references', payload);
	setRevision((current) => current + 1);
	return created;
}

export async function removeReference(referenceId: string): Promise<void> {
	await api.delete(`/api/references/${encodeURIComponent(referenceId)}`);
	setRevision((current) => current + 1);
}

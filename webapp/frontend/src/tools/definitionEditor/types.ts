import type { components } from '~/lib/api-schema';

export type Definition = components['schemas']['Definition'];
export type DefinitionField = components['schemas']['DefinitionField'];
export type DefinitionDraft = components['schemas']['DefinitionDraft'];
export type DefinitionEdit = components['schemas']['DefinitionEdit'];
export type SavedDraft = components['schemas']['SavedDraft'];
export type CatalogStatus = components['schemas']['CatalogStatus'];
export type DefinitionList = components['schemas']['DefinitionList'];
export type EditorRun = components['schemas']['EditorRun'];
export type EditorStage = components['schemas']['EditorStage'];
export type EditorKind = DefinitionDraft['kind'];

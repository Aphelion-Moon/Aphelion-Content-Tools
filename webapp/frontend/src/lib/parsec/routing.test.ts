import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const OPERATION_SURFACES = [
	'src/components/OpenFileActions.tsx',
	'src/components/SharedReferences.tsx',
	'src/tools/contentGraph/ContentGraphPage.tsx',
	'src/tools/contentGraph/ModularDebugPanel.tsx',
	'src/tools/fileManagement/ExportPanel.tsx',
	'src/tools/fileManagement/RepositoryPanel.tsx',
	'src/tools/fileManagement/ToolRunner.tsx',
	'src/tools/loreEditor/EntryEditor.tsx',
	'src/tools/loreEditor/GroupManager.tsx',
	'src/tools/loreEditor/LoreEditorPage.tsx',
	'src/tools/loreEditor/ReviewActions.tsx',
	'src/tools/parsec/ParsecPage.tsx',
] as const;

describe('Parsec operation routing', () => {
	it('routes operation feedback as typed events instead of generic notification wrappers', () => {
		const bypasses = OPERATION_SURFACES.filter((file) => {
			const source = readFileSync(resolve(file), 'utf8');
			return source.includes("~/lib/notify");
		});

		expect(bypasses).toEqual([]);
	});
});

import ExportPanel from './ExportPanel';
import RepositoryPanel from './RepositoryPanel';
import ToolRunner from './ToolRunner';

export default function FileManagementPage() {
	return (
		<>
			<ToolRunner />
			<RepositoryPanel
				repository="tool"
				heading="Aphelion Content Tools"
				blurb="This tool's own checkout — override JSON, group configuration, and the generated lore artifact live here."
			/>
			<RepositoryPanel
				repository="game"
				heading="Meridian-Rift"
				blurb="The game checkout. Pushes, pull requests, and complex merges stay in GitHub Desktop — this only makes local commits."
			/>
			<ExportPanel />
		</>
	);
}

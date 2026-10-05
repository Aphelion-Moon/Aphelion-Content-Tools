from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCapability(BaseModel):
	id: str
	route: str
	datasets: list[str] = Field(default_factory=list)
	operations: list[str] = Field(default_factory=list)
	search: list[str] = Field(default_factory=list)
	mutations: list[str] = Field(default_factory=list)
	integrations: list[str] = Field(default_factory=list)


class CapabilityStatus(BaseModel):
	capability: ToolCapability
	authoring_available: bool = True
	catalog_available: bool = True
	native_available: bool = True
	reason: str | None = None


CAPABILITIES = (
	ToolCapability(id='home', route='/'),
	ToolCapability(id='file-management', route='/file-management', mutations=['local-git', 'staged-lore-export']),
	ToolCapability(id='parsec', route='/parsec'),
	ToolCapability(id='lore-editor', route='/lore-editor', datasets=['lore'], search=['exact', 'full-text', 'semantic'], mutations=['canonical-draft']),
	*(ToolCapability(id=f'{kind}-editor', route=f'/{kind}-editor', datasets=['job-outfit-definitions'], operations=['catalog', 'analyze', 'validate', 'render', 'interactive'], search=['exact', 'structural', 'substring'], mutations=['canonical-draft', 'staged-game-apply'], integrations=['meridian-analyzer', 'byond']) for kind in ('outfit', 'job')),
	ToolCapability(id='graph', route='/graph', datasets=['content-graph'], search=['structural'], mutations=['staged-marker-edit']),
)

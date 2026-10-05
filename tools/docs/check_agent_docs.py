"""Validate agent-facing repository documentation and local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

REQUIRED_FILES = (
	"AGENTS.md",
	".agents/AGENTS.md",
	"references/maintainer-guide.md",
	"references/development/README.md",
	"references/development/backend-and-schema.md",
	"references/development/frontend-and-state.md",
	"references/development/data-and-generation.md",
	"references/development/content-graph.md",
	"references/development/export-safety.md",
	"references/development/verification.md",
	"references/development/meridian-integration.md",
	"references/development/platform-lifecycle-and-integrations.md",
)

REQUIRED_TEXT = {
	"AGENTS.md": (
		"Aphelion Content Tools",
		"references/maintainer-guide.md",
		"references/development/README.md",
		"tools/lore_editor/content/",
		"GitHub Desktop",
		"Every derived dataset",
		"revision-bound",
		"staged change-set standard",
	),
	"references/maintainer-guide.md": (
		"Normative status",
		"Shipped architecture: FastAPI and the Solid SPA",
		"Legacy pages are transitional and must not receive new product behavior",
		"Pydantic models are the canonical HTTP schema",
		"tools/lore_editor/content/ is canonical authored source",
		"platform life-cycle and integration guidance",
	),
	"references/development/backend-and-schema.md": (
		"Pydantic owns the HTTP schema",
		"stable error taxonomy",
		"framework-agnostic domain logic",
		'pip install -e ".[dev]"',
		"python -m ruff check .",
		"python -m pyright",
	),
	"references/development/frontend-and-state.md": (
		"one application shell",
		"one tool registry",
		"one typed API client",
		"one live-connection owner",
		"one shared application-store path",
		"npm run gen:api",
		"accessibility",
	),
	"references/development/data-and-generation.md": (
		"stable IDs",
		"schema and manifest versions",
		"record hashes",
		"projection generations",
		"deterministic",
		"artifact hashes",
		"AutoWiki",
	),
	"references/development/content-graph.md": (
		"modular_nova",
		"modular_aphelion",
		"NOVA",
		"APHELION",
		"loading",
		"failed",
	),
	"references/development/export-safety.md": (
		"tgstation.dme",
		"clean and conflict-free",
		"canonical-content revision",
		"source, base, and final hashes",
		"parent containment",
		"atomic replace",
		"rollback",
		"no force override",
	),
	"references/development/verification.md": (
		"python -m ruff check .",
		"python -m pyright",
		"python -m unittest discover",
		"Do not rerun monolithic",
		"bounded suite runner",
		"npm --prefix webapp/frontend run gen:api",
		"npm --prefix webapp/frontend test -- --run",
		"npm --prefix webapp/frontend run typecheck",
		"npm --prefix webapp/frontend run build",
		"git diff --check",
		"Command or real entry point:",
	),
	"references/development/meridian-integration.md": (
		"Meridian-Rift owns",
		"Content Tools owns",
		"Meridian-MCP owns",
		"PowerShell owns",
		"credentials never enter the browser",
	),
	"references/development/platform-lifecycle-and-integrations.md": (
		"Workspace currentness",
		"Immutable build and activation",
		"Search capabilities",
		"Shared context and references",
		"Tool and capability registration",
		"Game-repository changes",
		"Local and remote security boundary",
		"per-launch local session credential",
	),
}

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _local_link_error(markdown_file: Path, target: str) -> str | None:
	parsed = urlparse(target)
	if parsed.scheme or target.startswith("#"):
		return None
	path_text = unquote(parsed.path)
	if not path_text:
		return None
	resolved = (markdown_file.parent / path_text).resolve()
	if resolved.exists():
		return None
	return f"{markdown_file.as_posix()} has a broken local link: {target}"


def check_repository(root: Path) -> list[str]:
	"""Return documentation-policy errors for a repository root."""
	errors: list[str] = []
	root = root.resolve()
	for relative in REQUIRED_FILES:
		path = root / relative
		if not path.is_file():
			errors.append(f"missing required documentation: {relative}")

	agent_path = root / "AGENTS.md"
	if agent_path.is_file():
		agent_text = agent_path.read_text(encoding="utf-8")
		if "Aphelion Content Tools" not in agent_text:
			errors.append("AGENTS.md must identify Aphelion Content Tools")
		if "Meridian Rift agent instructions" in agent_text:
			errors.append("AGENTS.md must not contain Meridian-Rift game policy")

	compatibility_path = root / ".agents" / "AGENTS.md"
	if compatibility_path.is_file():
		compatibility_text = compatibility_path.read_text(encoding="utf-8")
		if (
			"../AGENTS.md" not in compatibility_text
			or "Aphelion Content Tools" not in compatibility_text
			or "Meridian Rift agent instructions" in compatibility_text
		):
			errors.append(
				".agents/AGENTS.md must point to the root Aphelion Content Tools policy"
			)

	for relative, needles in REQUIRED_TEXT.items():
		path = root / relative
		if not path.is_file():
			continue
		text = path.read_text(encoding="utf-8")
		for needle in needles:
			if needle not in text:
				errors.append(f"{relative} is missing required text: {needle}")

	for relative in REQUIRED_FILES:
		path = root / relative
		if not path.is_file():
			continue
		text = path.read_text(encoding="utf-8")
		for match in LINK_PATTERN.finditer(text):
			error = _local_link_error(path, match.group(1).strip().strip("<>"))
			if error:
				errors.append(error)

	ci_path = root / ".github" / "workflows" / "ci.yml"
	if ci_path.is_file():
		ci_text = ci_path.read_text(encoding="utf-8")
		if "python -m unittest discover" in ci_text:
			errors.append("CI must not run monolithic Python unittest discovery")
		if "tools/testing/run-python-suites.ps1" not in ci_text:
			errors.append("CI must run the bounded Python suite runner")
	for relative in (
		"tools/testing/python-suites.json",
		"tools/testing/run-python-suites.ps1",
		"tools/testing/suite_process.py",
		"tools/testing/suites.py",
	):
		if not (root / relative).is_file():
			errors.append(f"missing bounded Python test infrastructure: {relative}")
	return errors


def main() -> int:
	root = Path(__file__).resolve().parents[2]
	errors = check_repository(root)
	if errors:
		for error in errors:
			print(error)
		return 1
	print("Agent documentation is consistent.")
	return 0


if __name__ == "__main__":
	sys.exit(main())

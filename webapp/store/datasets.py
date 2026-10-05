from __future__ import annotations

from collections import Counter

from .snapshots import (
	CompatibilityDecision,
	DatasetBuild,
	DatasetRequirement,
	RepositoryIdentity,
)


def evaluate_compatibility(
	*,
	datasets: tuple[DatasetBuild, ...],
	requirements: tuple[DatasetRequirement, ...],
	selected_repositories: tuple[RepositoryIdentity, ...],
) -> CompatibilityDecision:
	"""Compare every dataset requirement and source revision with the selected workspace."""

	reasons: list[str] = []
	warnings: list[str] = []
	build_counts = Counter(build.kind for build in datasets)
	for kind, count in sorted(build_counts.items()):
		if count > 1:
			reasons.append(f"Dataset kind '{kind}' appears {count} times.")
	build_by_kind = {build.kind: build for build in datasets}
	selected_by_id = {repository.repository_id: repository for repository in selected_repositories}

	for requirement in sorted(requirements, key=lambda value: value.kind):
		build = build_by_kind.get(requirement.kind)
		if build is None:
			message = f"{'Required' if requirement.required else 'Optional'} dataset '{requirement.kind}' is missing."
			(reasons if requirement.required else warnings).append(message)
			continue
		if not build.diagnostics.succeeded:
			message = f"{'Required' if requirement.required else 'Optional'} dataset '{requirement.kind}' failed its build."
			(reasons if requirement.required else warnings).append(message)
			continue
		if build.schema_version not in requirement.accepted_schema_versions:
			message = (
				f"Dataset '{requirement.kind}' schema {build.schema_version} is not accepted; "
				f"expected one of {list(requirement.accepted_schema_versions)}."
			)
			(reasons if requirement.required else warnings).append(message)
		missing_capabilities = requirement.required_capabilities - build.capabilities
		if missing_capabilities:
			message = (
				f"{'Required' if requirement.required else 'Optional'} dataset '{requirement.kind}' lacks capabilities: "
				f"{', '.join(sorted(missing_capabilities))}."
			)
			(reasons if requirement.required else warnings).append(message)
		for source in build.sources:
			selected = selected_by_id.get(source.repository.repository_id)
			if selected is None:
				message = f"Dataset '{requirement.kind}' source repository '{source.repository.repository_id}' is not selected."
				(reasons if requirement.required else warnings).append(message)
			elif selected.revision != source.repository.revision:
				message = (
					f"Dataset '{requirement.kind}' source repository '{source.repository.repository_id}' revision "
					"does not match the selected workspace revision."
				)
				(reasons if requirement.required else warnings).append(message)

	return CompatibilityDecision(compatible=not reasons, reasons=tuple(reasons), warnings=tuple(warnings))

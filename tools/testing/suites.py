from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath


class SuiteManifestError(ValueError):
	"""Report an invalid or incomplete Python suite manifest."""


@dataclass(frozen=True)
class PythonSuite:
	"""Describe one bounded Python test process."""

	id: str
	description: str
	modules: tuple[str, ...]
	timeout_seconds: int
	max_log_bytes: int
	runner: str = "unittest"


@dataclass(frozen=True)
class SuiteManifest:
	"""Contain a complete, non-overlapping assignment of repository tests."""

	schema_version: int
	suites: tuple[PythonSuite, ...]


def _repository_pattern(value: object, suite_id: str) -> str:
	if not isinstance(value, str) or not value:
		raise SuiteManifestError(f"suite {suite_id!r} includes an invalid path pattern")
	path = PurePosixPath(value.replace("\\", "/"))
	if path.is_absolute() or ".." in path.parts:
		raise SuiteManifestError(f"suite {suite_id!r} patterns must be repository-relative: {value}")
	return path.as_posix()


def _positive_int(value: object, field: str, suite_id: str) -> int:
	if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
		raise SuiteManifestError(f"suite {suite_id!r} {field} must be a positive integer")
	return value


def _module_name(relative_path: Path) -> str:
	return ".".join(relative_path.with_suffix("").parts)


def load_suite_manifest(path: Path, repository_root: Path) -> SuiteManifest:
	"""Load and validate a complete, non-overlapping Python test-suite manifest."""

	repository_root = repository_root.resolve()
	payload = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(payload, dict) or payload.get("schema_version") != 1:
		raise SuiteManifestError("python suite manifest schema_version must be 1")
	raw_suites = payload.get("suites")
	if not isinstance(raw_suites, list) or not raw_suites:
		raise SuiteManifestError("python suite manifest must define at least one suite")

	raw_test_roots = payload.get("test_roots", ["."])
	if not isinstance(raw_test_roots, list) or not raw_test_roots:
		raise SuiteManifestError("python suite manifest must define at least one test root")
	test_roots = tuple(_repository_pattern(value, "manifest") for value in raw_test_roots)
	all_tests = {
		file.relative_to(repository_root)
		for relative_root in test_roots
		for file in (repository_root / relative_root).glob("**/test_*.py")
		if file.is_file()
	}
	assignments: dict[Path, list[str]] = {test: [] for test in all_tests}
	parsed: list[tuple[dict[str, object], tuple[Path, ...]]] = []
	seen_ids: set[str] = set()
	for raw_suite in raw_suites:
		if not isinstance(raw_suite, dict):
			raise SuiteManifestError("every python suite must be an object")
		suite_id = raw_suite.get("id")
		if not isinstance(suite_id, str) or not suite_id:
			raise SuiteManifestError("every python suite must have a non-empty id")
		if suite_id in seen_ids:
			raise SuiteManifestError(f"duplicate python suite id: {suite_id}")
		seen_ids.add(suite_id)
		raw_patterns = raw_suite.get("include")
		if not isinstance(raw_patterns, list) or not raw_patterns:
			raise SuiteManifestError(f"suite {suite_id!r} must include at least one path pattern")
		patterns = tuple(_repository_pattern(value, suite_id) for value in raw_patterns)
		matched = tuple(
			sorted(
				{
					file.relative_to(repository_root)
					for pattern in patterns
					for file in repository_root.glob(pattern)
					if file.is_file()
				}
			)
		)
		if not matched:
			raise SuiteManifestError(f"suite {suite_id!r} did not match any tests")
		for relative in matched:
			if relative not in assignments:
				raise SuiteManifestError(f"suite {suite_id!r} matched a non-test file: {relative.as_posix()}")
			assignments[relative].append(suite_id)
		parsed.append((raw_suite, matched))

	duplicates = sorted(path for path, owners in assignments.items() if len(owners) > 1)
	if duplicates:
		raise SuiteManifestError(
			"tests assigned to multiple suites: " + ", ".join(path.as_posix() for path in duplicates)
		)
	unassigned = sorted(path for path, owners in assignments.items() if not owners)
	if unassigned:
		raise SuiteManifestError("unassigned tests: " + ", ".join(path.as_posix() for path in unassigned))

	suites: list[PythonSuite] = []
	for raw_suite, matched in parsed:
		suite_id = str(raw_suite["id"])
		runner = raw_suite.get("runner", "unittest")
		if runner not in ("unittest", "pytest"):
			raise SuiteManifestError(f"suite {suite_id!r} runner must be unittest or pytest")
		description = raw_suite.get("description")
		if not isinstance(description, str) or not description:
			raise SuiteManifestError(f"suite {suite_id!r} must have a description")
		suites.append(
			PythonSuite(
				id=suite_id,
				runner=str(runner),
				description=description,
				modules=tuple(_module_name(relative) for relative in matched),
				timeout_seconds=_positive_int(raw_suite.get("timeout_seconds"), "timeout_seconds", suite_id),
				max_log_bytes=_positive_int(raw_suite.get("max_log_bytes"), "max_log_bytes", suite_id),
			)
		)
	return SuiteManifest(schema_version=1, suites=tuple(suites))


def main() -> int:
	parser = argparse.ArgumentParser(description="Validate and resolve the bounded Python suite manifest.")
	parser.add_argument("--manifest", type=Path, required=True)
	parser.add_argument("--repository-root", type=Path, required=True)
	args = parser.parse_args()
	manifest = load_suite_manifest(args.manifest, args.repository_root)
	print(json.dumps({"schema_version": manifest.schema_version, "suites": [asdict(suite) for suite in manifest.suites]}))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

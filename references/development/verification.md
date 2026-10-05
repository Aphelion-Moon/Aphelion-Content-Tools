# Verification

Run focused tests during development and the relevant larger gates before completion. Record each gate
separately; one successful unit test does not imply schema, browser, launcher, export, or game acceptance.

| Scope | Gate | Command or entry point | Required when |
| --- | --- | --- | --- |
| focused | Python behavior | `python -m unittest <test.module> -v` | Every backend/domain change |
| repository-wide | Python lint | `python -m ruff check .` | Every code or documentation-checker change |
| repository-wide | Python types | `python -m pyright` | Every production Python boundary change |
| repository-wide | Python tests | `./tools/testing/run-python-suites.ps1` | Before completion |
| integration | API schema | `npm --prefix webapp/frontend run gen:api` and inspect generated drift | Pydantic/API/frontend changes |
| repository-wide | Frontend tests | `npm --prefix webapp/frontend test -- --run` | Frontend or API contract changes |
| repository-wide | Frontend types | `npm --prefix webapp/frontend run typecheck` | Frontend or API contract changes |
| repository-wide | Production SPA | `npm --prefix webapp/frontend run build` | Frontend, package, or launcher changes |
| integration | Deterministic generation | `python tools/lore_editor/cli.py generate --repo-root .` then `python tools/lore_editor/cli.py validate --repo-root . --check-generated` | Canonical data/schema/generator changes |
| integration | Staged export | Prepare/apply against a dedicated clean compatible checkout, then prove dirty-checkout refusal | Export, manifest, repository, or generation changes |
| integration | Installed package | Build a wheel and import production modules outside the checkout | Packaging/dependency changes |
| integration | Real launcher | `cmd.exe /d /c '"Launch Aphelion Content Tools.cmd"'` | Launcher, bootstrap, server, or integrated UI changes |
| downstream | Meridian game | Meridian-Rift PowerShell compile/full build and relevant AutoWiki gate | Generated DM or integration changes |
| repository-wide | Diff hygiene | `git diff --check` plus `git status --short` | Every handoff |

Frontend interaction changes also require accessibility and keyboard coverage for the affected shared
flow. Launcher evidence includes the loopback URL/readiness marker, production SPA routes, and clean
shutdown. Export evidence identifies the stage manifest and proves that exactly the allowed artifact
changed. Downstream BYOND results must distinguish compile, initialization, AutoWiki artifacts, and
known environment limitations.

## Bounded Python suites

Do not rerun monolithic `python -m unittest discover` inside Codex. It destabilized or crashed the host
twice while executing the combined store, embedding, graph, worker, launcher, and other fixtures, and
never produced a final unittest summary. The exact responsible test/resource interaction is not yet
isolated.

The bounded suite runner reads `tools/testing/python-suites.json` and executes each selected group in a
separate owned process tree. Each group has a timeout and log-byte limit; the result records duration,
exit status, peak process-tree memory on Windows, log truncation, and `ResourceWarning` detection. It
writes logs and `summary.json` under the selected output directory without streaming test output into
Codex.

```powershell
# All required Python groups, sequentially.
./tools/testing/run-python-suites.ps1

# Focused bounded groups while iterating.
./tools/testing/run-python-suites.ps1 -Suite docs_and_testing,content_graph
```

Do not retry the full command to obtain a completion claim. Never terminate broad-matched Python
processes; the runner stops only the verified process tree it started. If a bounded group fails, inspect
its capped log, reproduce the exact named module if safe, and report the remaining groups rather than
falling back to monolithic discovery.

Workspace-currentness regression fixtures live under
`webapp/tests/fixtures/workspace_snapshots/`. The game-revision drift case must remain green: aggregate
workspace health is stale when either the catalog or Content Graph was built from a different selected
game revision, even when canonical lore projection health is current.

Use this report format:

```text
Command or real entry point:
Scope: focused | repository-wide | integration | downstream
Result:
Observed artifact/readiness marker:
Required gates not run:
Existing unrelated failures:
```

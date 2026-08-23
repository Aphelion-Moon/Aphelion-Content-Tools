# Verification

Run focused tests during development and the relevant larger gates before completion. Record each gate
separately; one successful unit test does not imply schema, browser, launcher, export, or game acceptance.

| Scope | Gate | Command or entry point | Required when |
| --- | --- | --- | --- |
| focused | Python behavior | `python -m unittest <test.module> -v` | Every backend/domain change |
| repository-wide | Python lint | `python -m ruff check .` | Every code or documentation-checker change |
| repository-wide | Python types | `python -m pyright` | Every production Python boundary change |
| repository-wide | Python tests | `python -m unittest discover` | Before completion |
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

Use this report format:

```text
Command or real entry point:
Scope: focused | repository-wide | integration | downstream
Result:
Observed artifact/readiness marker:
Required gates not run:
Existing unrelated failures:
```

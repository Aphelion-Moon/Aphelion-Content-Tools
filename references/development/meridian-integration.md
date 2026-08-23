# Meridian integration

The repositories have separate acceptance boundaries:

- Content Tools owns canonical structured data, Pydantic/schema evolution, the writer workflow,
  deterministic generation, stage manifests, and safe export.
- Meridian-Rift owns DreamMaker placement, module inclusion, full compilation, runtime behavior,
  AutoWiki integration, and final acceptance of the generated artifact.
- Meridian-MCP owns bounded DreamMaker source navigation, definition/context lookup, diagnostics, and
  supported map/runtime inspection. It does not replace the full game build or Content Tools tests.
- PowerShell owns deterministic Windows build and test orchestration, artifact checks, timeouts, and
  process cleanup.

Export only `modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm` into a compatible
clean checkout after manifest and hash validation. No editor implementation, raw authored records,
catalog projection, stage data, or browser credential crosses into the game repository.

AutoWiki publication remains CI-only and gated by repository secrets; credentials never enter the browser
or local content workflow. GitHub Desktop owns authenticated pushes, pull requests, and complex
merges. When generated output changes, report Content Tools generation/export evidence and
Meridian-Rift compilation/runtime/AutoWiki evidence as separate gates.

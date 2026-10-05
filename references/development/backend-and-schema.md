# Backend and schema

## Ownership

`webapp/api/` owns HTTP transport, dependency wiring, loopback policy, and OpenAPI. Routes validate
transport input and call focused services; they do not embed reconciliation, graph, export, Git, or
storage algorithms. `tools/lore_editor/`, `tools/content_graph/`, `webapp/store/`,
`webapp/git_adapter.py`, and `webapp/tooling.py` keep framework-agnostic domain logic and can be tested
without starting FastAPI.

Pydantic owns the HTTP schema. Models in `webapp/api/models.py` are the canonical request and response
definitions, OpenAPI source, and input to the generated TypeScript contract. Never add a separately
maintained frontend interface for the same payload. After a model changes, run `npm run gen:api` from
`webapp/frontend`, review `src/lib/api-schema.d.ts`, and update backend and frontend contract tests.

## Services, dependencies, and errors

Create the app through `create_app()` with explicit workspace roots so tests can isolate state.
Dependencies resolve repositories and shared services; avoid process-global current-workspace state.
Expected failures use the stable error taxonomy in `webapp/api/errors.py`. Preserve machine-readable
codes for malformed input, missing records, conflicts, incompatible game repositories, unavailable
stores, revisions, manifests, and filesystem failures. Do not turn expected domain failures into raw
exception strings or a blanket 400 response.

Validate and canonicalize paths before use, scope lookups to known collections, bound subprocess
output, and re-check repository state immediately before mutation. Long-running work belongs to the
workspace-bound worker with durable run metadata, bounded diagnostics, cancellation where practical,
and explicit recovery after a crash.

## Package and type boundary

The project must remain installable with:

```powershell
python -m pip install -e ".[dev]"
```

Use absolute package imports. Keep the declared Pyright production boundary honest; expanding it
requires fixing the newly included diagnostics rather than suppressing them globally. A schema or
backend change runs at least:

```powershell
python -m ruff check .
python -m pyright
./tools/testing/run-python-suites.ps1
npm --prefix webapp/frontend run gen:api
npm --prefix webapp/frontend run typecheck
```

Add focused tests for domain behavior, route status/code/payload, temporary-workspace isolation, and
generated schema consumption. Error messages should be actionable but stable program behavior belongs
in codes and typed fields, not prose matching.

## Shared request and write boundaries

`LocalSessionMiddleware` validates exact loopback Host/Origin and requires a per-launch HttpOnly,
SameSite session for API reads, all mutations, and live sockets. The SPA bootstraps `/api/session`
before mounting resources. Vite forwards only its own origin to the configured loopback backend.
Integration tests use `webapp.tests.http_client.TestClient` to establish a real session; boundary tests
use an unauthenticated client explicitly. Request and incoming socket sizes are bounded centrally.

`repository_write_lock` is reentrant within a thread and excludes other processes using an OS file
lock. Keep canonical multi-file operations within that lock and use `rollback_files` for exception
rollback. Publish derived multi-table updates through `staged_projection`: build a complete inactive
generation, then activate one pointer. Resolve one generation for each multi-table read.

Game-file tools use the workspace's `GameChangeSetService`. A tool supplies its explicit path allowlist,
expected bytes, and proposed bytes. Prepare returns a diff and opaque stage identifier; apply rechecks
compatibility, cleanliness, revision, containment, and hashes under the write lock. Successful apply
returns a receipt, and failed writes restore all touched files. Stages are bounded, expire after fifteen
minutes, and do not survive restart. Routes never accept replacement stage contents from the browser.

Worker pipe credentials and pipe identities rotate on each launch and respawn. Credentials travel in
the private child environment, never URLs, command arguments, files, or logs. Shutdown joins the delayed
optimizer before stopping the worker so a late callback cannot recreate it.

Authoring routes enter `AppContext.authoring()` inside the synchronous route operation. It holds the
write lock from the currentness check through the domain write; a dependency-only check leaves a race.
Do not hold thread-owned locks across yielding FastAPI dependencies, whose enter/exit may run on
different worker threads. Git adapter operations share the same reentrant repository coordinator.

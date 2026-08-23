# Frontend and state

The Solid SPA under `webapp/frontend/` is the target UI. Legacy files in `webapp/web/` and
`tools/*/web/` are transitional and must not receive new product behavior unless an explicit migration
step requires a compatibility fix.

## Shared concerns

The application has one application shell (`AppShell`), one tool registry, one typed API client,
one live-connection owner, and one shared application-store path (`appStore`). Import these facilities;
do not create parallel fetch wrappers, WebSockets, navigation registries, repository state, or global
stores. A tool page may own interaction state that no other page consumes.

`src/lib/api.ts` consumes the generated `api-schema.d.ts`. Run `npm run gen:api` after backend model
changes and review the generated diff. Shared formatting, notifications, reference presentation, and
open-file behavior belong in focused library or component units. Styles are component-scoped modules
unless a rule is genuinely global.

## Writer-facing behavior

Use content, review, conflict, catalog, stage, and repository language. Hide raw JSON, DM internals,
hashes, stack traces, and Git plumbing by default; expose them in a deliberate diagnostic view when
maintainers need them. Errors identify what failed, what remained unchanged, and the next safe action.
Loading, empty, failed, cancelled, stale, and completed states are distinct.

Both automated and browser accessibility checks are a completion requirement. Shared shell, search,
graph controls, and export flows need keyboard operation, useful labels, visible focus, and tests where
behavior can regress. Do not communicate status through color alone.

## Verification

For frontend changes, run focused Vitest tests plus API generation, the full suite, typecheck, and the
production build:

```powershell
npm --prefix webapp/frontend run gen:api
npm --prefix webapp/frontend test -- --run
npm --prefix webapp/frontend run typecheck
npm --prefix webapp/frontend run build
```

Integrated navigation, live updates, keyboard behavior, and launcher changes also require browser
exercise through the production FastAPI-served SPA and the real Windows launcher.

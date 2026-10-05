# Windows sidecar packaging spike

**Date:** 2026-08-24  
**Decision:** **No-go for Tauri integration until clean-checkout catalog bootstrap is made fast and offline-capable.**

The native Python sidecar itself is viable. The current catalog distribution and semantic rebuild path are
not yet viable as a writer's first-run experience, so Task 5.2 must not start from this state.

## Environment and artifact

- Windows 10 22H2, build 19045, x86-64.
- Python 3.13.2.
- PyInstaller 6.22.0 with pinned build dependencies in `packaging/requirements-build.txt`.
- PyInstaller `onedir` artifact containing FastAPI/Uvicorn, LanceDB, PyArrow, FastEmbed, ONNX Runtime,
  NumPy, Pillow, the production SPA, and the quantized `BAAI/bge-small-en-v1.5` model.
- Final measured build: 52.9 seconds, 987 files, 488,479,659 bytes (465.85 MiB); executable 12.63 MiB.
  The dependency set, not the executable, owns
  almost all installed size.

The model is copied from FastEmbed's verified local cache during this spike. A release build still needs
an explicit model download/revision/hash manifest; the spike configuration deliberately fails when the
model cache is absent instead of silently producing a keyword-only release.

## Runtime results

The artifact was run with Hugging Face offline flags against a disposable Aphelion checkout containing
the real 84,626-row projection and the real Meridian-Rift checkout as a read-only asset source.

| Gate | Result |
|---|---|
| Cold health response | 3.019–3.068 seconds across two measured starts |
| Store open | 84,626 rows; health reported 706.41 MiB active data |
| Hybrid search | 5 results for `radio` in 581–1,168 ms; semantic mode `hybrid` |
| Memory after search | 278.86 MiB working set; 585.41 MiB private bytes for the server |
| DMI preview | HTTP 200; rendered `icons/obj/service/bureaucracy.dmi`, state `paper` |
| Frozen worker | Generated the DM artifact successfully through the packaged worker mode |
| Final server + worker memory after search/generation | 411.3 MiB working set; 1,052.1 MiB private bytes |
| Normal shutdown | Server and worker both exited |
| Forced parent termination, before repair | Failed: worker remained orphaned |
| Forced parent termination, after repair | Passed: worker did not survive the parent |

The forced-shutdown repair uses a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. The
server assigns the persistent worker to that job immediately after spawn, so worker descendants inherit
the same kernel-owned lifetime. Focused source tests also prove closing the owner terminates an assigned
process and that worker crash/respawn still works.

## Rebuild and first-run results

The first realistic frozen rebuild exposed two independent problems.

1. The rebuild loaded all complete rows and their old vectors before beginning its nominal 500-row loop.
   It produced no progress checkpoint after 104 seconds and consumed about 3.2 GiB working set / 4.1 GiB
   private bytes across server and worker. It was cancelled.
2. FastEmbed's default native batch is 256 texts. Bounded LanceDB reads plus an application batch of 32
   reduced the source-path retest to about 677 MiB working set / 1.6 GiB private bytes. It reached
   500/20,881 catalog rows after roughly 112 seconds and 1,000/20,881 about 50 seconds later. Sustained
   throughput was therefore about 10 catalog texts/second, implying roughly 35 minutes for the catalog
   alone if that warm rate held. The retest was cancelled at 1,000 rows.

A separate clean-checkout launcher run had already exercised the current local catalog fallback. The
DreamMaker probe compiled with 0 errors and 0 warnings, but catalog activation remained active after more
than 15 minutes at approximately 2.6 GiB working set / 3.09 GiB private bytes and was cancelled. No
tracked `catalog-seed.json` currently gives a clean offline installation another path, and the existing
JSON seed format still embeds every target during activation.

Cancellation is cooperative: a stop requested during ONNX execution takes effect when native inference
returns to Python. In the measured batch-32 run that was within one bounded batch.

## Decision

The 465.85 MiB `onedir` sidecar, 3.1-second cold start, offline hybrid search, DMI support, and repaired
process-tree ownership are acceptable for a Windows desktop prototype. Packaging is not the blocker.

The release architecture is still a **no-go** because first-run catalog activation cannot reasonably ask
each writer's machine to regenerate the same 20,881 semantic vectors. Tauri would only hide that cost
behind a native window.

Before Task 5.2, replace the raw-target-only catalog seed with a versioned, hash-verified, compact
catalog projection that includes vectors and declares the store schema plus embedding model/revision.
Activation should import or atomically install those precomputed rows without ONNX inference. A local
DreamMaker rebuild remains the maintainer fallback, and keyword-only mode remains the explicit degraded
fallback when a compatible semantic projection is unavailable. This retains global hybrid search and
selected-context boosting without making first start depend on network access or a 30-plus-minute local
rebuild.

## Remaining packaging gates

- Add a reproducible, hash-verified model acquisition step instead of relying on a developer cache.
- Design and test the precomputed catalog-projection release asset.
- Run the installed-app test on a clean supported Windows machine after the catalog gate passes.
- Defer API launch-token, strict Host/Origin validation, signing, installer, updater, and rollback work to
  Tasks 5.2 and 5.3; none should be represented as complete by this spike.

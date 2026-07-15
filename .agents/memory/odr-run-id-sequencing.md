---
name: ODR run_id sequencing
description: build_odr must be called twice in the pipeline — first with placeholder run_id before the manifest exists, then rebuilt after manifest is built with the real run_id; only the second call produces the authoritative ODR.
---

## Rule

In `core/pipeline.py`, `build_odr()` is called twice:

1. **First call** — immediately after `assess_findings()`, before `build_run_manifest()`. Uses `run_id=""` as a placeholder. Its result is passed to `analysis_artifacts` for the gate counts. The classifications from this call are correct; the ODR itself is not yet canonical.

2. **Second call** — after `build_run_manifest()` returns (which produces `manifest.run_id`). Uses the real `run_id`. This is the authoritative ODR that gets written to `odr_{stamp}.json` and `odr_{stamp}.md`.

**Why:**

`build_run_manifest()` generates the `run_id` (a stable hash of the study and retrieval context). That ID must appear in every ODR entry's `odr_id` for the ODR to be independently linkable to the run. But `assess_findings()` must run before `build_run_manifest()`, and the gate/analysis counts need ODR entry count before the manifest call. So the two-call pattern is the correct architecture.

**How to apply:**

If you add any logic that needs the final canonical ODR (e.g., writing new artifact types that include ODR content), always use the result of the *second* `build_odr()` call, not the first. The first call's result lives only in `result_without_manifest`.

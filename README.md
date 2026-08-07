# Setup

## Repo layout (required convention)

```
Assets/, Packages/, ProjectSettings/   ← the actual Unity project. MUST live directly at repo
                                           root -- not nested in a subfolder, not as a raw .zip
                                           committed into git. This is required for the compile
                                           workflow to find anything.
spec_docs.zip                          ← the only file you manage by hand day-to-day. A zip of
                                           README.md, Architecture.md, ScriptsIndex.md, Scenes.md,
                                           Prefabs.md, Packages.md, ProjectVersion.txt,
                                           Dependencies.md, CodingGuidelines.md.
dataset/                               ← auto-created; the repair loop's mistake-log lives here.
tools/
  log_to_json.py                       ← bring this over from your existing repo (not included
                                           here -- this is the one file we never had a copy of).
  diff_errors.py
  append_repair_history.py
.github/workflows/
  1-generate-and-push.yml              ← OPTIONAL/legacy HTTP-based generation trigger. The
                                           notebook's Step 10a (git sync) is the recommended path
                                           now -- more reliable for a job that can take 20-60+ min.
  3-compile-only.yml
  4-package-and-report.yml
kaggle_notebook/
  Unified_Generate_Repair_Server.ipynb
```

## Secrets

**On Kaggle** (this notebook's Add-ons → Secrets):
- `API_KEY` — any string you make up (shared secret for the `/repair` endpoint)
- `NGROK_AUTH_TOKEN` — from `dashboard.ngrok.com/get-started/your-authtoken`
- `GITHUB_PAT` — a GitHub Personal Access Token with `repo` scope, used by Step 10a to pull docs
  and push generated output directly

**On GitHub** (repo Settings → Secrets and variables → Actions):
- `UNITY_LICENSE`, `UNITY_EMAIL`, `UNITY_PASSWORD` — your Unity CI credentials
- `NGROK_URL`, `API_KEY` — only needed if you're using workflow 1 (legacy path) or wiring
  `/repair` calls into the compile workflow

## Day-to-day use (now fully automatic after these 3 manual steps)

1. **Upload `spec_docs.zip`** to the repo root (GitHub web UI, drag-and-drop).
2. **Run the notebook** through Step 4, then **Step 10b** (the unified `/generate` + `/repair`
   job server + ngrok tunnel). Copy the printed URL into `NGROK_URL`.
3. **Trigger workflow 1** (`workflow_dispatch`, or just push a change to `spec_docs.zip` — that
   alone triggers it).

Everything after that is automatic, no further manual steps:

```
workflow 1 (generate) --push--> workflow 3 (compile) --on completion--> workflow 4
                                                                            |
                                                          errors? --yes--> auto-repair
                                                                            |
                                                          recompile to verify the fix actually worked
                                                                            |
                                                          log verified/unverified fixes to
                                                          dataset/repair_history.jsonl and commit
```

Workflow 1 and workflow 4's repair step both **wait up to 4 minutes** for the Kaggle server to
become reachable (polling `/health`) before giving up — covers the case where the workflow fires
before the notebook has finished loading the model.

**Watch it happen live:** open the `NGROK_URL` directly in a browser (no auth needed for this
page) — it's a self-refreshing dashboard showing every generate/repair job, its state, and
timing, updating every 5 seconds.

## One honest uncertainty in this version

The "after repair, recompile to verify" step in workflow 4 constructs a log folder by hand
(`extracted_logs_after/compile-and-send/...`) to feed `log_to_json.py`, since that in-progress
run doesn't have a completed run ID to fetch real Actions logs from via the API the normal way.
This mimics the confirmed-working folder/filename pattern as closely as possible, but I still
don't have `log_to_json.py`'s actual source (GitHub blocks automated access to it) — if this
specific step errors out, that's the first place to look, and pasting the error back will let me
fix it precisely instead of guessing again.

## What changed in this version

- **SetupRunner.cs is now mandatory, not just requested** — the planning prompt requires it with
  an embedded example, and if the model somehow still omits it, the notebook force-injects a
  plan entry for it rather than silently producing a project without one.
- **Generation no longer depends on ngrok surviving a long HTTP round-trip** — Step 10a pulls and
  pushes directly via git instead.
- **The notebook now asks loudly for missing secrets** (ngrok token, GitHub PAT) instead of
  silently falling back to a placeholder and printing one easy-to-miss warning line.
- **Workflow 4's zip step is now a whitelist** (`Assets`/`Packages`/`ProjectSettings` only) instead
  of a blacklist — the previous version could pick up stray files/zips sitting in the repo root
  and produce a zip with no usable project content, which is exactly what happened before.

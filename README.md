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

## Day-to-day use

1. Zip your docs → upload as `spec_docs.zip` at repo root (via GitHub's web UI, drag-and-drop).
2. In the Kaggle notebook: run Steps 0/1/3/4 (env, deps, model+adapter, generation helper), then
   **Step 10a** — pulls the docs, generates, pushes the result back via git. No ngrok needed for
   this part.
3. That push triggers `3-compile-only.yml` automatically, which triggers `4-package-and-report.yml`
   on completion — download `UnityProject.zip` + `CompilerErrors.json` from that run's artifacts.
4. For the repair loop (compile errors → auto-fix → verify → log), run the notebook's **Step 10b**
   (the `/repair` job server + ngrok tunnel) and wire its URL into a workflow step that POSTs to
   `/repair` — see the earlier `2-compile-and-repair.yml` design in this project's history for the
   full pattern (recompile-and-diff loop), adapted to call the async `/repair` endpoint.

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

#!/usr/bin/env python3
"""Compares two CompilerErrors.json reports (before/after a repair attempt) and classifies
each ORIGINAL error as resolved, persisted, or not_attempted (the repair server never touched
that file). Also flags any NEW errors present in `after` that weren't in `before`, for files the
repair server DID touch -- a fix that resolves one error while introducing another is a partial
failure worth logging, not a clean success.

ASSUMED SCHEMA (matches what the Kaggle repair-server notebook already reads from
CompilerErrors.json) -- adjust _error_key() below if your tools/log_to_json.py uses different
field names:
    {"errorCount": N, "errors": [{"file": "...", "line": N, "column": N,
                                   "code": "CS0246", "message": "..."}]}
"""
import json
import argparse


def _error_key(err):
    # (file, code) is the stable match key -- line numbers shift after an edit, and the
    # message text can vary slightly (e.g. it includes a changing identifier name) even for
    # what's conceptually "the same" error. If a file has two DIFFERENT errors with the same
    # code, they'll collapse into one key here -- rare in practice, and the "persisted" /
    # "resolved" classification degrades gracefully (worst case: undercounts resolutions),
    # rather than crashing.
    return (err["file"], err["code"])


def classify(before_path, after_path, touched_files):
    with open(before_path) as f:
        before = json.load(f).get("errors", [])
    with open(after_path) as f:
        after = json.load(f).get("errors", [])

    before_keys = {_error_key(e): e for e in before}
    after_keys = {_error_key(e): e for e in after}

    results = []
    for key, err in before_keys.items():
        file = key[0]
        if file not in touched_files:
            status = "not_attempted"
        elif key not in after_keys:
            status = "resolved"
        else:
            status = "persisted"
        results.append({**err, "status": status})

    new_errors_introduced = [
        {**err, "status": "newly_introduced"}
        for key, err in after_keys.items()
        if key not in before_keys and err["file"] in touched_files
    ]

    return results, new_errors_introduced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="CompilerErrors.json from the ORIGINAL compile")
    ap.add_argument("--after", required=True, help="CompilerErrors.json from the RECOMPILE after repair")
    ap.add_argument("--touched-files", required=True,
                     help="JSON file: a list of file paths the repair server actually changed "
                          "(the 'changed' array from its X-Repair-Summary response header)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.touched_files) as f:
        touched = set(json.load(f))

    results, new_errors = classify(args.before, args.after, touched)

    resolved = sum(1 for r in results if r["status"] == "resolved")
    persisted = sum(1 for r in results if r["status"] == "persisted")
    not_attempted = sum(1 for r in results if r["status"] == "not_attempted")

    print(f"Resolved: {resolved} | Persisted (still broken): {persisted} | "
          f"Not attempted: {not_attempted} | Newly introduced: {len(new_errors)}")

    with open(args.out, "w") as f:
        json.dump({"results": results, "new_errors_introduced": new_errors}, f, indent=2)


if __name__ == "__main__":
    main()

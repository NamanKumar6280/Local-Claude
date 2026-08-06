#!/usr/bin/env python3
"""Builds/appends (error -> fix) training records to dataset/repair_history.jsonl, using
diff_errors.py's classification plus the original and repaired project zips to pull the actual
before/after file content for each touched file.

Only records with status != "not_attempted" are written -- there's no point storing a pair for
a file the repair server never touched. `verified` is True only when the specific error
genuinely disappeared on recompile -- that's the field to filter on later when actually
fine-tuning on this data, since "persisted" and "newly_introduced" records are still valuable to
KEEP (they're evidence of what the model gets wrong), just not as positive training examples.
"""
import argparse
import json
import os
import zipfile
from collections import defaultdict


def load_zip_text(zip_path, member):
    with zipfile.ZipFile(zip_path) as zf:
        try:
            return zf.read(member).decode("utf-8", errors="ignore")
        except KeyError:
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff-json", required=True)
    ap.add_argument("--original-zip", required=True, help="UnityProject.zip from BEFORE repair")
    ap.add_argument("--repaired-zip", required=True, help="the zip returned by the repair server")
    ap.add_argument("--run-id-before", required=True)
    ap.add_argument("--run-id-after", required=True)
    ap.add_argument("--history-path", default="dataset/repair_history.jsonl")
    args = ap.parse_args()

    with open(args.diff_json) as f:
        diff = json.load(f)

    by_file = defaultdict(list)
    for err in diff["results"]:
        by_file[err["file"]].append(err)
    for err in diff["new_errors_introduced"]:
        by_file[err["file"]].append(err)

    os.makedirs(os.path.dirname(args.history_path) or ".", exist_ok=True)
    written = 0
    with open(args.history_path, "a", encoding="utf-8") as out:
        for file, errors in by_file.items():
            if all(e["status"] == "not_attempted" for e in errors):
                continue
            original = load_zip_text(args.original_zip, file)
            fixed = load_zip_text(args.repaired_zip, file)
            if original is None or fixed is None:
                continue  # file path mismatch between report and zip -- skip rather than guess
            for err in errors:
                if err["status"] == "not_attempted":
                    continue
                record = {
                    "file": file,
                    "error_code": err.get("code"),
                    "error_message": err.get("message"),
                    "line": err.get("line"),
                    "original_content": original,
                    "fixed_content": fixed,
                    "status": err["status"],
                    "verified": err["status"] == "resolved",
                    "compile_run_before": args.run_id_before,
                    "compile_run_after": args.run_id_after,
                }
                out.write(json.dumps(record) + "\n")
                written += 1

    print(f"Appended {written} record(s) to {args.history_path}")


if __name__ == "__main__":
    main()

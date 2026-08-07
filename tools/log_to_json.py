#!/usr/bin/env python3
"""
GitHub Actions log -> CompilerErrors.json

Takes whatever the CI produced -- a single Unity log, a directory of raw
step logs downloaded from GitHub Actions, or the logs .zip itself -- finds
the Unity compilation log inside it, strips the GitHub layer (timestamps,
ANSI colour, ##[group]/::workflow:: commands), extracts every Unity C#
diagnostic including multi-line ones, setup/SDK errors, environment issues,
classifies and dedupes them, and writes a structured report.
"""
import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import Counter, OrderedDict

# ---------------------------------------------------------------------------
# GitHub Actions log de-noising
# ---------------------------------------------------------------------------

TIMESTAMP_RE = re.compile(r"^﻿?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")
ANSI_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\)?)"
)
HASH_CMD_RE = re.compile(r"^##\[(?P<cmd>[a-zA-Z]+)\](?P<rest>.*)$")
COLON_CMD_RE = re.compile(r"^::(?P<cmd>[a-zA-Z-]+)(?P<params>\s[^:]*)?::(?P<rest>.*)$")

DROP_COMMANDS = {
    "group", "endgroup", "debug", "section", "add-mask", "set-output",
    "save-state", "add-matcher", "remove-matcher", "add-path", "set-env",
    "echo", "stop-commands", "command",
}

NOISE_PREFIXES = (
    "Requested labels:", "Job defined at:", "Waiting for a runner",
    "Runner name:", "Runner group", "Machine name:", "Current runner version",
    "Operating System", "Runner Image", "Image:", "Version:",
    "Included Software", "Image Release:", "Testing runner upgrade",
    "Download action repository", "Getting action download info",
    "Evaluating condition for step", "Complete job name:",
    "Cleaning up orphan processes", "Post job cleanup", "Prepare all required actions",
    "Uploading artifact", "Artifact ", "Starting digest computation",
    "##[", "shell: ", "env:", "with:",
)


def strip_github_formatting(raw_line):
    line = raw_line.rstrip("\r\n")
    line = TIMESTAMP_RE.sub("", line)
    line = ANSI_RE.sub("", line)
    line = line.replace("\x00", "")

    m = HASH_CMD_RE.match(line)
    if m:
        if m.group("cmd").lower() in DROP_COMMANDS:
            return None
        return m.group("rest")

    m = COLON_CMD_RE.match(line)
    if m:
        if m.group("cmd").lower() in DROP_COMMANDS:
            return None
        return m.group("rest")

    return line


# ---------------------------------------------------------------------------
# Unity / Roslyn diagnostics & General Engine Errors/Warnings
# ---------------------------------------------------------------------------

DIAG_RE = re.compile(
    r"""^\s*
        (?:\[[^\]]{0,60}\]\s*)?                     
        (?P<file>(?:[A-Za-z]:[\\/])?[^\s(][^()]*?\.(?i:cs))
        \(\s*(?P<line>\d+)\s*,\s*(?P<col>\d+)\s*\)
        \s*:\s*
        (?P<severity>error|warning)\s+(?P<code>CS\d{2,5})
        \s*:\s*(?P<message>.*)$
    """,
    re.VERBOSE,
)

NOLOC_DIAG_RE = re.compile(
    r"^\s*(?P<severity>error|warning)\s+(?P<code>CS\d{2,5})\s*:\s*(?P<message>.*)$"
)

# Added to parse Unity engine, SDK, and PlayerPrefs errors/warnings without file paths
GENERIC_LOG_RE = re.compile(
    r"""^\s*
        (?:\[\s*(?P<tag>Error|Warning|Exception|Assert)\s*\])?\s*
        (?:(?P<severity>error|warning):?)?\s*
        (?P<message>
            (?:Failed to find package|Library folder does not exist|Rebuilding Library|Unable to load player prefs|PlayerPrefs - Creating folder).*
        )$
    """,
    re.VERBOSE | re.IGNORECASE,
)

RECORD_START_RE = re.compile(
    r"^\s*(?:"
    r"Assets[/\\]|Packages[/\\]|Library[/\\]|ProjectSettings[/\\]|Temp[/\\]|"
    r"[A-Za-z]:[\\/]|-----|=====|\*\*\*|\[|\d+\)\s|"
    r"Compilation (?:failed|succeeded)|Scripts have compiler errors|"
    r"Unloading |Refreshing |Reloading |Begin MonoManager|Initialize engine|"
    r"Mono config path|Registering|Loading |Unloading |Preloading |"
    r"Build completed|Build Finished|Aborting batchmode|DisplayProgressbar|"
    r"Exiting batchmode|Cancelling DisplayDialog|Package Manager|Fatal Error|"
    r"Warning:|Error:"
    r")"
)

CONTINUATION_RE = re.compile(r"^(?:\s+\S|[a-z(),'\"\[\]<>+.\-]|\.\.\.)")

MAX_CONTINUATION_LINES = 12
MAX_MESSAGE_CHARS = 2000

UNITY_MARKERS = (
    "Unity Editor version", "-----CompilerOutput", "Compilation failed",
    "Scripts have compiler errors", "batchmode", "Batchmode",
    "Packages/manifest.json", "Refreshing native plugins",
    "Initialize engine version", "unity-builder", "Unity.exe", "/opt/unity",
    "Assets/", "error CS", "warning CS", "Begin MonoManager", "PlayerPrefs",
)

DEFAULT_INPUTS = (
    "logs",
    "logs.zip",
    "Logs/compile.log",
    "Logs",
)

STEP_NUM_RE = re.compile(r"^\d+_")
STEP_NAME_HINTS = (
    "compile project", "batchmode", "unity-builder", "build project",
    "compile", "unity", "build", "editor",
)
STEP_NAME_ANTIHINTS = (
    "set up job", "complete job", "post ", "checkout", "cache ", "restore",
    "upload", "download", "generate structured", "error_warning", "package ",
    "copy instructions", "system", "runner", "cleanup", "fail the job",
)


def find_default_input():
    for candidate in DEFAULT_INPUTS:
        if os.path.exists(candidate):
            return candidate
    return None


TYPE_NAMESPACE_HINTS = {
    "InputValue": "UnityEngine.InputSystem",
    "InputAction": "UnityEngine.InputSystem",
    "InputActionAsset": "UnityEngine.InputSystem",
    "PlayerInput": "UnityEngine.InputSystem",
    "TMP_Text": "TMPro",
    "TextMeshProUGUI": "TMPro",
    "TextMeshPro": "TMPro",
    "CinemachineVirtualCamera": "Cinemachine",
    "CinemachineBrain": "Cinemachine",
    "UniversalRenderPipelineAsset": "UnityEngine.Rendering.Universal",
    "UniversalAdditionalCameraData": "UnityEngine.Rendering.Universal",
    "GraphicsSettings": "UnityEngine.Rendering",
    "RenderPipelineAsset": "UnityEngine.Rendering",
    "VolumeProfile": "UnityEngine.Rendering",
    "NavMesh": "UnityEngine.AI",
    "NavMeshAgent": "UnityEngine.AI",
    "NavMeshBuilder": "UnityEditor.AI",
    "NavMeshSurface": "Unity.AI.Navigation",
    "AssetDatabase": "UnityEditor",
    "EditorUtility": "UnityEditor",
    "PrefabUtility": "UnityEditor",
    "BuildPipeline": "UnityEditor",
    "SceneManager": "UnityEngine.SceneManagement",
    "EditorSceneManager": "UnityEditor.SceneManagement",
    "Image": "UnityEngine.UI",
    "Button": "UnityEngine.UI",
    "Canvas": "UnityEngine",
    "Lightmapping": "UnityEditor",
    "VisualElement": "UnityEngine.UIElements",
    "Job": "Unity.Jobs",
    "Entity": "Unity.Entities",
    "float3": "Unity.Mathematics",
}

NAMESPACE_PACKAGE_HINTS = {
    "UnityEngine.InputSystem": "com.unity.inputsystem",
    "TMPro": "com.unity.textmeshpro",
    "Cinemachine": "com.unity.cinemachine",
    "UnityEngine.Rendering.Universal": "com.unity.render-pipelines.universal",
    "Unity.AI.Navigation": "com.unity.ai.navigation",
    "Unity.Entities": "com.unity.entities",
    "Unity.Mathematics": "com.unity.mathematics",
    "Unity.Jobs": "com.unity.jobs",
    "UnityEngine.ProBuilder": "com.unity.probuilder",
    "Unity.Netcode": "com.unity.netcode.gameobjects",
    "UnityEngine.Timeline": "com.unity.timeline",
    "UnityEngine.Localization": "com.unity.localization",
    "Unity.VisualScripting": "com.unity.visualscripting",
    "UnityEngine.Splines": "com.unity.splines",
}

BUILTIN_NAMESPACES = {
    "UnityEngine", "UnityEditor", "UnityEngine.AI", "UnityEditor.AI",
    "UnityEngine.UI", "UnityEngine.Rendering", "UnityEngine.SceneManagement",
    "EditorSceneManager", "UnityEngine.UIElements", "UnityEditor.Build",
    "System", "System.Collections", "System.Collections.Generic", "System.Linq",
    "System.IO", "System.Text", "System.Threading.Tasks",
}

MISSING_TYPE_RE = re.compile(
    r"type or namespace name '([A-Za-z0-9_]+)(?:<[^']*>)?'"
    r"(?:.*?could not be found|.*?does not exist)", re.S
)
MISSING_NAMESPACE_RE = re.compile(
    r"type or namespace name '([A-Za-z0-9_]+)(?:<[^']*>)?' does not exist in the namespace '([^']+)'"
)
CANNOT_CONVERT_RE = re.compile(r"cannot (?:implicitly )?convert (?:from )?'([^']+)' to '([^']+)'")
NO_DEFINITION_RE = re.compile(
    r"'([A-Za-z0-9_.<>]+)' does not contain a definition for '([A-Za-z0-9_]+)'"
)
NAME_NOT_EXIST_RE = re.compile(r"[Tt]he name '([A-Za-z0-9_]+)' does not exist in the current context")
AMBIGUOUS_RE = re.compile(r"'([A-Za-z0-9_]+)' is an ambiguous reference between '([^']+)' and '([^']+)'")
NOT_IMPLEMENTED_RE = re.compile(r"'([^']+)' does not implement (?:interface|inherited abstract) member '([^']+)'")
INACCESSIBLE_RE = re.compile(r"'([^']+)' is inaccessible due to its protection level")
METADATA_FILE_RE = re.compile(r"[Mm]etadata file '([^']+)' could not be found")
NO_ARGUMENT_RE = re.compile(r"[Tt]here is no argument given that corresponds to the required (?:formal )?parameter '([^']+)'")
BAD_ARG_COUNT_RE = re.compile(r"[Nn]o overload for (?:method )?'([^']+)' takes (\d+) arguments")

CODE_KINDS = {
    "CS0246": "missing_type",
    "CS0234": "missing_namespace",
    "CS0103": "unresolved_name",
    "CS0117": "missing_member",
    "CS1061": "missing_member",
    "CS1503": "bad_conversion",
    "CS0029": "bad_conversion",
    "CS0266": "bad_conversion",
    "CS1502": "bad_conversion",
    "CS7036": "bad_arguments",
    "CS1501": "bad_arguments",
    "CS1729": "bad_arguments",
    "CS0104": "ambiguous_reference",
    "CS0535": "missing_implementation",
    "CS0534": "missing_implementation",
    "CS0122": "inaccessible",
    "CS0006": "unresolved_reference",
    "CS0400": "unresolved_reference",
    "CS0111": "duplicate_definition",
    "CS0101": "duplicate_definition",
    "CS0161": "missing_return",
    "CS0165": "unassigned_variable",
    "CS0618": "deprecated_api",
    "CS0619": "deprecated_api",
    "CS1002": "syntax",
    "CS1003": "syntax",
    "CS1022": "syntax",
    "CS1513": "syntax",
    "CS1519": "syntax",
    "CS1525": "syntax",
    "CS0106": "invalid_modifier",
    "CS0116": "syntax",
    "UNITY_SETUP": "project_setup",
}

MISSING_ASSET_RES = (
    re.compile(r"[Cc]ould not find (?:file|asset) '?\"?([^'\"\n]+)"),
    re.compile(r"[Tt]he file '([^']+)' could not be (?:found|loaded)"),
    re.compile(r"Failed to (?:load|import) (?:asset|package) at path:?\s*(\S+)"),
    re.compile(r"Missing (?:asset|prefab|scene):\s*(\S+)"),
    re.compile(r"GUID \[?([0-9a-fA-F]{32})\]? is missing"),
)
UNRESOLVED_REF_RES = (
    re.compile(r"[Uu]nable to resolve reference '?([^'\s]+)"),
    re.compile(r"[Rr]eference '([^']+)' not found"),
    re.compile(r"Assembly '([^']+)' will not be loaded"),
    re.compile(r"[Mm]issing assembly reference:?\s*'?([^'\s]+)"),
)


def iter_candidate_files(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.lower().endswith((".zip", ".png", ".jpg", ".gz", ".pyc", ".json")):
                continue
            yield os.path.join(dirpath, name)


def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except (OSError, UnicodeError):
        return []


def step_name_of(path):
    name = os.path.basename(path.replace("\\", "/")).lower()
    name = os.path.splitext(name)[0]
    return STEP_NUM_RE.sub("", name)


def score_log_file(path, lines):
    diagnostics = 0
    markers = 0
    for line in lines:
        cleaned = strip_github_formatting(line)
        if cleaned is None:
            continue
        if DIAG_RE.match(cleaned) or NOLOC_DIAG_RE.match(cleaned) or GENERIC_LOG_RE.match(cleaned):
            diagnostics += 1
        else:
            for marker in UNITY_MARKERS:
                if marker in cleaned:
                    markers += 1
                    break

    step = step_name_of(path)
    name_score = sum(1 for h in STEP_NAME_HINTS if h in step)
    if any(h in step for h in STEP_NAME_ANTIHINTS):
        name_score -= 10
    return (diagnostics, name_score, min(markers, 200)), diagnostics


def select_log_files(root):
    scored = []
    for path in iter_candidate_files(root):
        lines = read_lines(path)
        if not lines:
            continue
        score, diagnostics = score_log_file(path, lines)
        scored.append((score, diagnostics, path, lines))

    if not scored:
        return None, [], []

    scored.sort(key=lambda t: t[2])
    scored.sort(key=lambda t: t[0], reverse=True)
    best = scored[0]
    if best[1] > 0:
        return best[2], [(best[2], best[3])], scored
    return best[2], [(p, ls) for _s, _d, p, ls in scored], scored


def extract_zip(zip_path, workdir):
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = os.path.normpath(os.path.join(workdir, member))
            if not target.startswith(os.path.normpath(workdir) + os.sep):
                continue
            if member.endswith("/"):
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return workdir


def normalize_path(path):
    p = path.strip().strip("\"'").replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    first = p.split("/", 1)[0]
    absolute = p.startswith("/") or ":" in first
    if absolute:
        for root in ("/Assets/", "/Packages/", "/ProjectSettings/"):
            idx = p.find(root)
            if idx > 0:
                return p[idx + 1:]
    if p.startswith("./"):
        p = p[2:]
    return p


def parse_lines(lines, source):
    records = []
    current = None
    continuation_count = 0

    for raw in lines:
        cleaned = strip_github_formatting(raw)
        if cleaned is None:
            continue
        stripped = cleaned.strip()

        m = DIAG_RE.match(cleaned)
        if m:
            current = {
                "code": m.group("code"),
                "severity": m.group("severity"),
                "file": normalize_path(m.group("file")),
                "line": int(m.group("line")),
                "column": int(m.group("col")),
                "message": m.group("message").strip(),
                "source": source,
            }
            records.append(current)
            continuation_count = 0
            continue

        m = NOLOC_DIAG_RE.match(cleaned)
        if m:
            current = {
                "code": m.group("code"),
                "severity": m.group("severity"),
                "file": None,
                "line": 0,
                "column": 0,
                "message": m.group("message").strip(),
                "source": source,
            }
            records.append(current)
            continuation_count = 0
            continue

        # Check for un-pathed build configuration warnings or environment problems
        m = GENERIC_LOG_RE.match(cleaned)
        if m:
            severity = m.group("severity") or ("warning" if "warning" in cleaned.lower() or "folder does not exist" in cleaned.lower() or "unable to load" in cleaned.lower() else "error")
            current = {
                "code": "UNITY_SETUP",
                "severity": severity.lower(),
                "file": None,
                "line": 0,
                "column": 0,
                "message": m.group("message").strip(),
                "source": source,
            }
            records.append(current)
            continuation_count = 0
            continue

        if current is not None and stripped:
            if (continuation_count < MAX_CONTINUATION_LINES
                    and len(current["message"]) < MAX_MESSAGE_CHARS
                    and not RECORD_START_RE.match(cleaned)
                    and not any(stripped.startswith(p) for p in NOISE_PREFIXES)
                    and CONTINUATION_RE.match(cleaned)):
                current["message"] = (current["message"] + " " + stripped).strip()
                continuation_count += 1
                continue
        current = None

    return records


def scan_environment_issues(lines):
    missing_assets, unresolved = set(), set()
    for raw in lines:
        cleaned = strip_github_formatting(raw)
        if cleaned is None:
            continue
        for rx in MISSING_ASSET_RES:
            m = rx.search(cleaned)
            if m:
                missing_assets.add(normalize_path(m.group(1)))
        for rx in UNRESOLVED_REF_RES:
            m = rx.search(cleaned)
            if m:
                unresolved.add(m.group(1).strip())
    return missing_assets, unresolved


def classify(code, message):
    kind = CODE_KINDS.get(code, "other")
    hint = {"kind": kind}

    if code == "UNITY_SETUP":
        hint.update({"kind": "project_setup", "message": message})
        return hint

    m = MISSING_NAMESPACE_RE.search(message)
    if m:
        full = f"{m.group(2)}.{m.group(1)}"
        hint.update({"kind": "missing_namespace", "type": m.group(1),
                     "namespace": m.group(2), "fullNamespace": full})
        pkg = NAMESPACE_PACKAGE_HINTS.get(full) or NAMESPACE_PACKAGE_HINTS.get(m.group(2))
        if pkg:
            hint["suggestedPackage"] = pkg
        return hint

    m = MISSING_TYPE_RE.search(message)
    if m:
        name = m.group(1)
        if name in NAMESPACE_PACKAGE_HINTS or name in BUILTIN_NAMESPACES:
            hint.update({"kind": "missing_namespace", "namespace": name, "fullNamespace": name})
            pkg = NAMESPACE_PACKAGE_HINTS.get(name)
            if pkg:
                hint["suggestedPackage"] = pkg
            return hint
        hint.update({"kind": "missing_type", "type": name})
        ns = TYPE_NAMESPACE_HINTS.get(name)
        if ns:
            hint["suggestedUsing"] = ns
            pkg = NAMESPACE_PACKAGE_HINTS.get(ns)
            if pkg:
                hint["suggestedPackage"] = pkg
        return hint

    return hint


KIND_PRIORITY = {
    "project_setup": 1,
    "unresolved_reference": 1,
    "missing_namespace": 1,
    "syntax": 2,
    "duplicate_definition": 2,
    "invalid_modifier": 2,
    "missing_type": 3,
    "unresolved_name": 3,
    "missing_member": 3,
    "ambiguous_reference": 3,
    "bad_conversion": 4,
    "bad_arguments": 4,
    "missing_implementation": 4,
    "inaccessible": 4,
    "missing_return": 4,
    "unassigned_variable": 5,
    "deprecated_api": 5,
    "other": 4,
}


def priority_of(hint):
    if hint.get("suggestedPackage") or hint.get("kind") == "project_setup":
        return 1
    return KIND_PRIORITY.get(hint.get("kind"), 4)


def repair_hint_text(entry):
    h = entry["hint"]
    kind = h.get("kind")
    if kind == "project_setup":
        return "Project environment or SDK warning detected - check Android SDK installations, caching configurations, or folder paths."
    if kind == "missing_type":
        t = h.get("type", "the type")
        return f"'{t}' is unknown here: add the appropriate namespace/using directive or assembly reference."
    return "No specific pattern matched - read the message and verify the configuration."


def dedupe(entries):
    seen = OrderedDict()
    for e in entries:
        key = (e["code"], e["file"], e["line"], e["column"], e["message"])
        if key in seen:
            seen[key]["occurrences"] += 1
        else:
            e["occurrences"] = 1
            seen[key] = e
    out = list(seen.values())
    out.sort(key=lambda e: (e["file"] or "", e["line"], e["column"], e["code"]))
    return out


def derive_missing_info(errors):
    missing_classes, missing_namespaces = set(), set()
    missing_packages, unresolved_names, unresolved_refs = set(), set(), set()
    for e in errors:
        h = e["hint"]
        kind = h.get("kind")
        if h.get("suggestedPackage"):
            missing_packages.add(h["suggestedPackage"])
        if kind == "missing_type" and h.get("type"):
            missing_classes.add(h["type"])
    return (sorted(missing_classes), sorted(missing_namespaces), sorted(missing_packages),
            sorted(unresolved_names), sorted(unresolved_refs))


def build_summary(errors, warnings):
    by_code = Counter(e["code"] for e in errors)
    by_kind = Counter(e["hint"]["kind"] for e in errors)
    by_file = Counter(e["file"] or "<no file>" for e in errors)
    return {
        "byCode": dict(by_code.most_common()),
        "byKind": dict(by_kind.most_common()),
        "byFile": dict(by_file.most_common()),
        "filesAffected": sorted({e["file"] for e in errors if e["file"]}),
        "topFiles": [{"file": f, "errors": n} for f, n in by_file.most_common(5)],
        "warningCodes": dict(Counter(w["code"] for w in warnings).most_common()),
    }


def annotate(kind, message):
    print(f"::{kind}::{message}", file=sys.stderr)


def build_report(scan_root, run_number, quiet=False):
    primary, scanned, scored = select_log_files(scan_root)

    if primary is None:
        annotate("error", f"No readable log files found under '{scan_root}'.")
        return None, 2

    raw_records, all_lines = [], []
    for path, lines in scanned:
        raw_records.extend(parse_lines(lines, os.path.basename(path)))
        all_lines.extend(lines)

    for r in raw_records:
        r["hint"] = classify(r["code"], r["message"])
        r["priority"] = priority_of(r["hint"])
        r["repairHint"] = repair_hint_text(r)

    errors = dedupe([r for r in raw_records if r["severity"] == "error"])
    warnings = dedupe([r for r in raw_records if r["severity"] == "warning"])

    (missing_classes, missing_namespaces, missing_packages,
     unresolved_names, unresolved_refs) = derive_missing_info(errors)
    missing_assets, unresolved_from_log = scan_environment_issues(all_lines)
    unresolved_refs = sorted(set(unresolved_refs) | unresolved_from_log)

    fix_order = [
        {"file": e["file"], "line": e["line"], "code": e["code"],
         "kind": e["hint"]["kind"], "priority": e["priority"]}
        for e in sorted(errors, key=lambda e: (e["priority"], e["file"] or "", e["line"]))
    ]

    report = {
        "cycle": run_number,
        "compile": "FAILED" if errors else "PASSED",
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "summary": build_summary(errors, warnings),
        "missingClasses": missing_classes,
        "missingNamespaces": missing_namespaces,
        "missingPackages": missing_packages,
        "missingAssets": sorted(missing_assets),
        "unresolvedReferences": unresolved_refs,
        "unresolvedNames": unresolved_names,
        "fixOrder": fix_order,
        "source": {
            "input": scan_root,
            "primaryLog": primary,
            "primaryStep": step_name_of(primary),
            "filesScanned": [p for p, _ in scanned],
            "candidatesConsidered": len(scored),
            "linesRead": len(all_lines),
        },
    }
    return report, 0


def print_human_report(report, limit=None):
    src = report["source"]
    print(f"input      : {src['input']}")
    print(f"parsed log : {src['primaryLog']}")
    print(f"result     : {report['compile']}  ({report['errorCount']} errors, {report['warningCount']} warnings)")

    def show(entries, title):
        if not entries:
            return
        print(f"\n{title} ({len(entries)})")
        print("-" * 78)
        for e in entries[:limit] if limit else entries:
            loc = f"{e['file']}({e['line']},{e['column']})" if e["file"] else "<no file>"
            print(f"[P{e['priority']}] {loc}: {e['code']} [{e['hint']['kind']}]")
            print(f"      {e['message']}")
            print(f"      -> {e['repairHint']}")

    show(report["errors"], "ERRORS")
    show(report["warnings"], "WARNINGS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_pos", nargs="?", metavar="LOG")
    ap.add_argument("--log", "--input", "-i", dest="log")
    ap.add_argument("--run-number", default="0")
    ap.add_argument("--out-dir")
    ap.add_argument("--out-name", default="CompilerErrors.json")
    ap.add_argument("--test", "--dry-run", dest="test", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--summary-file")
    ap.add_argument("--fail-on-error", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    log_input = args.log or args.input_pos
    if not log_input:
        log_input = find_default_input()
        if log_input is None:
            annotate("error", "No log given.")
            return 2

    tmpdir = None
    scan_root = log_input
    try:
        if zipfile.is_zipfile(log_input):
            tmpdir = tempfile.mkdtemp(prefix="ghlogs-")
            scan_root = extract_zip(log_input, tmpdir)
        report, code = build_report(scan_root, int(args.run_number or 0), quiet=args.quiet or args.test)
        if report is None:
            return code
    finally:
        if tmpdir:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    if args.test:
        print_human_report(report, limit=args.limit)
    elif args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        out_path = os.path.join(args.out_dir, args.out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    else:
        json.dump(report, sys.stdout, indent=2)
        print()

    if args.fail_on_error and report["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

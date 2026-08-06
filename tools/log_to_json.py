#!/usr/bin/env python3
"""
GitHub Actions log -> CompilerErrors.json

Takes whatever the CI produced -- a single Unity log, a directory of raw
step logs downloaded from GitHub Actions, or the logs .zip itself -- finds
the Unity compilation log inside it, strips the GitHub layer (timestamps,
ANSI colour, ##[group]/::workflow:: commands), extracts every Unity C#
diagnostic including the multi-line ones, classifies and dedupes them, and
writes a structured report the repair model can consume directly.

Usage:
    # on GitHub Actions, no path needed -- it finds whatever the workflow
    # produced (see DEFAULT_INPUTS below)
    python3 log_to_json.py --run-number "$GITHUB_RUN_NUMBER" --out-dir BuildReports

    # or name the input explicitly
    python3 log_to_json.py --log Logs/compile.log ...   # compile-check.yml
    python3 log_to_json.py --log logs/ ...              # parser.yml, unzipped
    python3 log_to_json.py --log logs.zip ...           # parser.yml, raw download

    # trial run on any saved log: prints what it extracted, writes nothing
    python3 log_to_json.py somelog.txt --test
    python3 log_to_json.py tools/sample_actions_log.txt --test

    # no --out-dir and no --test -> the JSON goes to stdout (pipe it anywhere)
    python3 log_to_json.py somelog.txt > CompilerErrors.json

A missing input is a hard failure (exit 2), never "0 errors" -- a broken
pipeline and a clean compile must never look the same. That distinction is
why the -logFile path in the workflow must stay inside /github/workspace;
see the README.
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

# Every line in a downloaded raw log is prefixed with an ISO-8601 timestamp:
#   2026-08-04T11:58:23.1234567Z Assets/Foo.cs(3,5): error CS0246: ...
TIMESTAMP_RE = re.compile(r"^﻿?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")

# CSI / OSC escape sequences (game-ci colourises its output).
ANSI_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\)?)"
)

# Runner annotations: ##[group]Run ... / ##[error]msg / ##[debug]msg
HASH_CMD_RE = re.compile(r"^##\[(?P<cmd>[a-zA-Z]+)\](?P<rest>.*)$")

# Workflow commands: ::error file=a.cs,line=1::message / ::group::name
COLON_CMD_RE = re.compile(r"^::(?P<cmd>[a-zA-Z-]+)(?P<params>\s[^:]*)?::(?P<rest>.*)$")

# Annotations that carry no diagnostic payload at all.
DROP_COMMANDS = {
    "group", "endgroup", "debug", "section", "add-mask", "set-output",
    "save-state", "add-matcher", "remove-matcher", "add-path", "set-env",
    "echo", "stop-commands", "command",
}

# Pure workflow bookkeeping -- never part of a Unity diagnostic.
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
    """Return the payload of a raw Actions log line, or None to drop it.

    Handles the three layers GitHub wraps around program output: the ISO
    timestamp prefix, ANSI colour codes, and runner/workflow annotations.
    Anything that isn't an annotation passes through untouched (so a plain
    Unity log parses identically -- this is a no-op on clean input).
    """
    line = raw_line.rstrip("\r\n")
    line = TIMESTAMP_RE.sub("", line)
    line = ANSI_RE.sub("", line)
    line = line.replace("\x00", "")

    m = HASH_CMD_RE.match(line)
    if m:
        if m.group("cmd").lower() in DROP_COMMANDS:
            return None
        # ##[error]Assets/Foo.cs(3,5): error CS0246: ... -> keep the payload
        return m.group("rest")

    m = COLON_CMD_RE.match(line)
    if m:
        if m.group("cmd").lower() in DROP_COMMANDS:
            return None
        return m.group("rest")

    return line


# ---------------------------------------------------------------------------
# Unity / Roslyn diagnostics
# ---------------------------------------------------------------------------

# Assets/Scripts/PlayerController.cs(32,10): error CS0246: The type or
# namespace name 'InputValue' could not be found (are you missing a using
# directive or an assembly reference?)
DIAG_RE = re.compile(
    r"""^\s*
        (?:\[[^\]]{0,60}\]\s*)?                     # optional [tag] Unity prefixes
        (?P<file>(?:[A-Za-z]:[\\/])?[^\s(][^()]*?\.(?i:cs))
        \(\s*(?P<line>\d+)\s*,\s*(?P<col>\d+)\s*\)
        \s*:\s*
        (?P<severity>error|warning)\s+(?P<code>CS\d{2,5})
        \s*:\s*(?P<message>.*)$
    """,
    re.VERBOSE,
)

# Same diagnostic without a location (assembly-level errors like CS0006).
NOLOC_DIAG_RE = re.compile(
    r"^\s*(?P<severity>error|warning)\s+(?P<code>CS\d{2,5})\s*:\s*(?P<message>.*)$"
)

# Lines that start a *new* record of some kind, so they can never be the
# continuation of the diagnostic above them.
RECORD_START_RE = re.compile(
    r"^\s*(?:"
    r"Assets[/\\]|Packages[/\\]|Library[/\\]|ProjectSettings[/\\]|Temp[/\\]|"
    r"[A-Za-z]:[\\/]|-----|=====|\*\*\*|\[|\d+\)\s|"
    r"Compilation (?:failed|succeeded)|Scripts have compiler errors|"
    r"Unloading |Refreshing |Reloading |Begin MonoManager|Initialize engine|"
    r"Mono config path|Registering|Loading |Unloading |Preloading |"
    r"Build completed|Build Finished|Aborting batchmode|DisplayProgressbar|"
    r"Exiting batchmode|Cancelling DisplayDialog|Package Manager|Fatal Error"
    r")"
)

# A wrapped diagnostic continues with indentation, or with a lowercase word /
# punctuation -- e.g. "directive or an assembly reference?)" or the indented
# overload list Roslyn prints under CS1503.
CONTINUATION_RE = re.compile(r"^(?:\s+\S|[a-z(),'\"\[\]<>+.\-]|\.\.\.)")

MAX_CONTINUATION_LINES = 12
MAX_MESSAGE_CHARS = 2000

# Markers used to decide which file in a log bundle is the Unity compile log.
UNITY_MARKERS = (
    "Unity Editor version", "-----CompilerOutput", "Compilation failed",
    "Scripts have compiler errors", "batchmode", "Batchmode",
    "Packages/manifest.json", "Refreshing native plugins",
    "Initialize engine version", "unity-builder", "Unity.exe", "/opt/unity",
    "Assets/", "error CS", "warning CS", "Begin MonoManager",
)

# ---------------------------------------------------------------------------
# Where the logs actually are on GitHub Actions
# ---------------------------------------------------------------------------

# `gh api repos/:owner/:repo/actions/runs/:id/logs` (what parser.yml calls)
# returns a zip laid out like this -- one whole-job transcript at the root,
# plus one file per step inside a folder named after the job:
#
#   0_compile.txt                                        <- whole job
#   compile/1_Set up job.txt
#   compile/4_Compile project (batchmode, no build).txt   <- the one we want
#   compile/5_Generate structured error_warning report.txt
#   compile/system.txt
#
# The step numbers and the step name both change whenever compile-check.yml is
# edited, so nothing may hardcode "4_Compile project ...". We score every file
# instead and let the diagnostics decide, using the step name only as a
# tiebreak between files that look equally plausible.
DEFAULT_INPUTS = (
    "logs",              # parser.yml: unzip -o logs.zip -d logs
    "logs.zip",          # parser.yml: the raw `gh api ... /logs` download
    "Logs/compile.log",  # compile-check.yml: Unity's own -logFile
    "Logs",
)

# Strip the "4_" that GitHub prefixes onto every step log's filename.
STEP_NUM_RE = re.compile(r"^\d+_")

# Step names that mean "this file is Unity compiling".
STEP_NAME_HINTS = (
    "compile project", "batchmode", "unity-builder", "build project",
    "compile", "unity", "build", "editor",
)
# Pure runner bookkeeping -- cheap to rule out by name, and ruling them out
# matters because step 5 echoes this script's own output back into the log.
STEP_NAME_ANTIHINTS = (
    "set up job", "complete job", "post ", "checkout", "cache ", "restore",
    "upload", "download", "generate structured", "error_warning", "package ",
    "copy instructions", "system", "runner", "cleanup", "fail the job",
)


def find_default_input():
    """First of DEFAULT_INPUTS that exists, or None.

    Lets both workflows call this script with no path at all: the layout is
    fixed by the workflow, not by whoever is running it.
    """
    for candidate in DEFAULT_INPUTS:
        if os.path.exists(candidate):
            return candidate
    return None

# ---------------------------------------------------------------------------
# Knowledge used to turn a raw message into an actionable hint
# ---------------------------------------------------------------------------

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

# Namespaces that ship with the editor -- a missing one means a using
# directive / asmdef reference, never a package install.
BUILTIN_NAMESPACES = {
    "UnityEngine", "UnityEditor", "UnityEngine.AI", "UnityEditor.AI",
    "UnityEngine.UI", "UnityEngine.Rendering", "UnityEngine.SceneManagement",
    "UnityEditor.SceneManagement", "UnityEngine.UIElements", "UnityEditor.Build",
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

# code -> (kind, repair hint template)
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
}

# Non-compiler failures worth surfacing so the model doesn't chase a missing
# file as if it were a code bug.
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


# ---------------------------------------------------------------------------
# Input discovery
# ---------------------------------------------------------------------------

def iter_candidate_files(root):
    """Yield every plausible text log under `root` (file, dir, already-extracted zip)."""
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
    """'compile/4_Compile project (batchmode, no build).txt' -> 'compile project (batchmode, no build)'."""
    name = os.path.basename(path.replace("\\", "/")).lower()
    name = os.path.splitext(name)[0]
    return STEP_NUM_RE.sub("", name)


def score_log_file(path, lines):
    """How much does this file look like the Unity compilation log?

    Returns ((diagnostics, name_score, marker_score), diagnostics) -- a tiered
    ranking key, compared left to right:

      1. diagnostics -- the file with the most real CS diagnostics always wins.
         No filename can talk us out of the file that has the errors in it.
      2. name_score  -- breaks the tie between the whole-job transcript
         (0_compile.txt) and the compile step's own log, which necessarily hold
         the *same* diagnostics. The step log wins: it contains only Unity's
         output, so the environment scan can't pick up file listings printed by
         the packaging step or this script's own echoed output.
      3. marker_score -- last resort for logs with no diagnostics at all.
    """
    diagnostics = 0
    markers = 0
    for line in lines:
        cleaned = strip_github_formatting(line)
        if cleaned is None:
            continue
        if DIAG_RE.match(cleaned) or NOLOC_DIAG_RE.match(cleaned):
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
    """Pick the Unity compile log out of a bundle of raw step logs.

    Returns (primary_path, scanned_paths, all_scored). If the best candidate
    holds no diagnostics at all we fall back to scanning every candidate --
    an unusual layout should degrade to "slower" not "silently empty".
    """
    scored = []
    for path in iter_candidate_files(root):
        lines = read_lines(path)
        if not lines:
            continue
        score, diagnostics = score_log_file(path, lines)
        scored.append((score, diagnostics, path, lines))

    if not scored:
        return None, [], []

    # Two stable passes: path ascending, then rank descending -- so equal-ranked
    # files always resolve the same way instead of depending on walk order.
    scored.sort(key=lambda t: t[2])
    scored.sort(key=lambda t: t[0], reverse=True)
    best = scored[0]
    if best[1] > 0:
        return best[2], [(best[2], best[3])], scored
    # Nothing looked like a diagnostic anywhere -- hand back everything so the
    # parser (and the empty-result warning) sees the whole bundle.
    return best[2], [(p, ls) for _s, _d, p, ls in scored], scored


def extract_zip(zip_path, workdir):
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            # Refuse path traversal out of workdir.
            target = os.path.normpath(os.path.join(workdir, member))
            if not target.startswith(os.path.normpath(workdir) + os.sep):
                continue
            if member.endswith("/"):
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return workdir


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def normalize_path(path):
    """Make the file path repo-relative so it matches what's in UnityProject.zip."""
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
    """Extract diagnostics (with multi-line messages) from one log's lines."""
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

        # Multi-line diagnostic: Roslyn wraps long messages and indents the
        # candidate-overload list under CS1503/CS7036.
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
    """Non-CS failures: assets Unity couldn't find, references it couldn't resolve."""
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


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(code, message):
    """Structured description of *what kind of fix* this needs, so the repair
    model gets a head start instead of only raw text."""
    kind = CODE_KINDS.get(code, "other")
    hint = {"kind": kind}

    m = MISSING_NAMESPACE_RE.search(message)
    if m:
        # CS0234 names the *leaf* and its parent: 'Universal' in
        # 'UnityEngine.Rendering' means UnityEngine.Rendering.Universal is
        # what's actually missing -- that's the name a package maps to.
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
        # `using TMPro;` failing reports the *namespace* as an unknown type.
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

    m = CANNOT_CONVERT_RE.search(message)
    if m:
        hint.update({"kind": "bad_conversion", "from": m.group(1), "to": m.group(2)})
        return hint

    m = NO_DEFINITION_RE.search(message)
    if m:
        hint.update({"kind": "missing_member", "type": m.group(1), "member": m.group(2)})
        return hint

    m = NAME_NOT_EXIST_RE.search(message)
    if m:
        hint.update({"kind": "unresolved_name", "name": m.group(1)})
        ns = TYPE_NAMESPACE_HINTS.get(m.group(1))
        if ns:
            hint["suggestedUsing"] = ns
        return hint

    m = AMBIGUOUS_RE.search(message)
    if m:
        hint.update({"kind": "ambiguous_reference", "name": m.group(1),
                     "candidates": [m.group(2), m.group(3)]})
        return hint

    m = NOT_IMPLEMENTED_RE.search(message)
    if m:
        hint.update({"kind": "missing_implementation", "type": m.group(1), "member": m.group(2)})
        return hint

    m = INACCESSIBLE_RE.search(message)
    if m:
        hint.update({"kind": "inaccessible", "member": m.group(1)})
        return hint

    m = METADATA_FILE_RE.search(message)
    if m:
        hint.update({"kind": "unresolved_reference", "reference": m.group(1)})
        return hint

    m = NO_ARGUMENT_RE.search(message)
    if m:
        hint.update({"kind": "bad_arguments", "parameter": m.group(1)})
        return hint

    m = BAD_ARG_COUNT_RE.search(message)
    if m:
        hint.update({"kind": "bad_arguments", "method": m.group(1), "given": int(m.group(2))})
        return hint

    return hint


# Fix order that actually converges: environment/config first (one missing
# package can manufacture a dozen type errors), then cascading syntax damage,
# then ordinary code errors. Lower number = fix earlier.
KIND_PRIORITY = {
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
    """1 = fix first. A missing package outranks the type errors it caused."""
    if hint.get("suggestedPackage"):
        return 1
    return KIND_PRIORITY.get(hint.get("kind"), 4)


def repair_hint_text(entry):
    """One sentence telling the repair model where to start on this error."""
    h = entry["hint"]
    kind = h.get("kind")
    if kind == "missing_type":
        t = h.get("type", "the type")
        if h.get("suggestedPackage"):
            return (f"'{t}' lives in {h['suggestedUsing']} which ships with package "
                    f"{h['suggestedPackage']}. Add the using directive; if the package "
                    f"isn't installed, report it instead of editing manifest.json.")
        if h.get("suggestedUsing"):
            return f"Add 'using {h['suggestedUsing']};' to {entry.get('file') or 'the file'}."
        return (f"'{t}' is unknown here: add the right using directive, check the spelling, "
                f"or add the defining assembly to this asmdef's references.")
    if kind == "missing_namespace":
        ns = h.get("fullNamespace") or h.get("namespace", "")
        pkg = h.get("suggestedPackage")
        base = (f"Namespace '{ns}' isn't visible here - the using path is wrong, or the "
                f"assembly isn't referenced by this asmdef.")
        return base + (f" It ships with package {pkg}; report the dependency instead of "
                       f"editing manifest.json." if pkg else "")
    if kind == "unresolved_name":
        return (f"'{h.get('name')}' isn't declared in scope: check for a missing field/local, "
                f"a using directive, or a typo.")
    if kind == "missing_member":
        return (f"'{h.get('type')}' has no member '{h.get('member')}' in this Unity version - "
                f"find the current API (it may have moved to another class or namespace).")
    if kind == "bad_conversion":
        frm, to = h.get("from", "?"), h.get("to", "?")
        if frm.endswith("GameObject") and to.endswith("Transform"):
            return "Pass '.transform' of the GameObject; fix the call site, not the method signature."
        return f"Convert '{frm}' to '{to}' at the call site, or change the argument that's being passed."
    if kind == "bad_arguments":
        return "Argument list doesn't match any overload - check the current signature before changing it."
    if kind == "ambiguous_reference":
        return (f"'{h.get('name')}' is ambiguous between {', '.join(h.get('candidates', []))} - "
                f"fully qualify it or drop one using directive.")
    if kind == "missing_implementation":
        return f"Implement '{h.get('member')}' on '{h.get('type')}'."
    if kind == "inaccessible":
        return f"'{h.get('member')}' isn't accessible here - use a public API instead of widening access."
    if kind == "unresolved_reference":
        return (f"Assembly/reference '{h.get('reference', 'unknown')}' couldn't be resolved - "
                f"this is an asmdef or package problem, not a code bug.")
    if kind == "duplicate_definition":
        return "Same type/member defined twice - remove the duplicate, likely a leftover copy of a file."
    if kind == "syntax":
        return "Syntax error - the real cause is usually a few lines above the reported position."
    if kind == "deprecated_api":
        return "Deprecated API - the message names the replacement; use it."
    if kind == "missing_return":
        return "Not all code paths return a value."
    return "No specific pattern matched - read the message and fix at the reported location."


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def dedupe(entries):
    """Collapse identical diagnostics (Unity repeats them per assembly pass)."""
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
    """Roll the per-error hints up into the project-level "what's missing" lists."""
    missing_classes, missing_namespaces = set(), set()
    missing_packages, unresolved_names, unresolved_refs = set(), set(), set()
    for e in errors:
        h = e["hint"]
        kind = h.get("kind")
        if h.get("suggestedPackage"):
            missing_packages.add(h["suggestedPackage"])
        if kind == "missing_type" and h.get("type"):
            missing_classes.add(h["type"])
            ns = h.get("suggestedUsing")
            if ns and ns not in BUILTIN_NAMESPACES:
                missing_namespaces.add(ns)
        elif kind == "missing_namespace":
            ns = h.get("fullNamespace") or h.get("namespace")
            if ns and ns not in BUILTIN_NAMESPACES:
                missing_namespaces.add(ns)
        elif kind == "unresolved_name" and h.get("name"):
            unresolved_names.add(h["name"])
        elif kind == "unresolved_reference" and h.get("reference"):
            unresolved_refs.add(h["reference"])
        elif kind == "missing_member" and h.get("type"):
            unresolved_names.add(f"{h['type']}.{h.get('member', '')}".rstrip("."))
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def annotate(kind, message):
    print(f"::{kind}::{message}", file=sys.stderr)


def build_report(scan_root, run_number, quiet=False):
    primary, scanned, scored = select_log_files(scan_root)

    if primary is None:
        annotate("error", f"No readable log files found under '{scan_root}'.")
        return None, 2

    if not quiet and len(scored) > 1:
        print(f"Scanned {len(scored)} log file(s); using: {primary}")

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

    # Root-cause-first list for the repair model; `errors` itself stays sorted
    # by file/line so a human reading the report can follow along.
    fix_order = [
        {"file": e["file"], "line": e["line"], "code": e["code"],
         "kind": e["hint"]["kind"], "priority": e["priority"]}
        for e in sorted(errors, key=lambda e: (e["priority"], e["file"] or "", e["line"]))
    ]

    repair_hints = []
    for e in sorted(errors, key=lambda e: e["priority"]):
        if e["repairHint"] not in repair_hints:
            repair_hints.append(e["repairHint"])

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
        "repairHints": repair_hints,
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
    """Readable dump of everything that was extracted -- what --test shows."""
    src = report["source"]
    print(f"input      : {src['input']}")
    print(f"parsed log : {src['primaryLog']}")
    print(f"step       : {src.get('primaryStep', '?')}"
          f"  ({src.get('candidatesConsidered', 1)} candidate file(s) considered)")
    print(f"lines read : {src['linesRead']}")
    print(f"result     : {report['compile']}  "
          f"({report['errorCount']} errors, {report['warningCount']} warnings)")

    def show(entries, title):
        if not entries:
            return
        print(f"\n{title} ({len(entries)})")
        print("-" * 78)
        for e in entries[:limit] if limit else entries:
            loc = f"{e['file']}({e['line']},{e['column']})" if e["file"] else "<no file>"
            dup = f"  x{e['occurrences']}" if e.get("occurrences", 1) > 1 else ""
            print(f"[P{e['priority']}] {loc}: {e['code']} [{e['hint']['kind']}]{dup}")
            print(f"      {e['message']}")
            print(f"      -> {e['repairHint']}")
        if limit and len(entries) > limit:
            print(f"      ... and {len(entries) - limit} more")

    show(report["errors"], "ERRORS")
    show(report["warnings"], "WARNINGS")

    buckets = [
        ("missing classes/types", report["missingClasses"]),
        ("missing namespaces", report["missingNamespaces"]),
        ("possible missing packages", report["missingPackages"]),
        ("missing assets", report["missingAssets"]),
        ("unresolved references", report["unresolvedReferences"]),
        ("unresolved names", report["unresolvedNames"]),
    ]
    if any(v for _k, v in buckets):
        print("\nDETECTED ISSUES")
        print("-" * 78)
        for label, values in buckets:
            if values:
                print(f"  {label}: {', '.join(values)}")

    if report["summary"]["byCode"]:
        print("\nBY CODE: " + ", ".join(f"{c}={n}" for c, n in report["summary"]["byCode"].items()))
        print("BY KIND: " + ", ".join(f"{k}={n}" for k, n in report["summary"]["byKind"].items()))


def main():
    ap = argparse.ArgumentParser(
        description="Turn a Unity / GitHub Actions log into CompilerErrors.json",
        epilog="Trial run on a saved log:  python log_to_json.py mylog.txt --test")
    ap.add_argument("input_pos", nargs="?", metavar="LOG",
                    help="same as --log, given positionally")
    ap.add_argument("--log", "--input", "-i", dest="log",
                    help="Unity log file, directory of raw Actions logs, or logs .zip")
    ap.add_argument("--run-number", default="0",
                    help="GitHub run number, written to the report as 'cycle'")
    ap.add_argument("--out-dir",
                    help="where to write the report; omit to print the JSON to stdout")
    ap.add_argument("--out-name", default="CompilerErrors.json")
    ap.add_argument("--test", "--dry-run", dest="test", action="store_true",
                    help="parse and print a readable breakdown; write no files")
    ap.add_argument("--limit", type=int, default=None,
                    help="with --test/--summary-file, only show the first N errors/warnings")
    ap.add_argument("--summary-file",
                    help="append the readable breakdown here as Markdown; pass "
                         "\"$GITHUB_STEP_SUMMARY\" to put it on the Actions run page")
    ap.add_argument("--fail-on-error", action="store_true",
                    help="Exit 1 when the report contains compile errors")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    log_input = args.log or args.input_pos
    if not args.test and not args.out_dir:
        # No destination and not a trial run -> JSON goes to stdout; keep the
        # console chatter out of it.
        args.quiet = True

    if not log_input:
        # Neither workflow needs to spell the path out: the layout is fixed by
        # the workflow that produced it, so look for it.
        log_input = find_default_input()
        if log_input is None:
            annotate("error",
                     f"No log given, and none of the paths the workflows produce exist "
                     f"({', '.join(DEFAULT_INPUTS)}) relative to {os.getcwd()}. Either "
                     f"the step that produces the log didn't run, or this script wasn't "
                     f"invoked from the repository root.")
            return 2
        if not args.quiet:
            print(f"No --log given; found workflow output: {log_input}")

    if not os.path.exists(log_input):
        # HARD FAIL -- this used to silently produce an empty report. A missing
        # log is a pipeline bug, not "0 errors"; those must never look alike.
        annotate("error",
                 f"Log input not found at '{log_input}'. For Logs/compile.log this almost "
                 f"always means the -logFile path Unity was given isn't inside the "
                 f"container/runner mount it can actually write to (see "
                 f".github/workflows/compile-check.yml). For 'logs/' it means the "
                 f"`gh api .../logs` download or the unzip in parser.yml failed.")
        return 2

    try:
        run_number = int(args.run_number)
    except (TypeError, ValueError):
        run_number = 0

    tmpdir = None
    scan_root = log_input
    try:
        if zipfile.is_zipfile(log_input):
            tmpdir = tempfile.mkdtemp(prefix="ghlogs-")
            scan_root = extract_zip(log_input, tmpdir)
        report, code = build_report(scan_root, run_number, quiet=args.quiet or args.test)
        if report is None:
            return code
        report["source"]["input"] = log_input
    finally:
        if tmpdir:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    if args.summary_file:
        try:
            with open(args.summary_file, "a", encoding="utf-8") as f:
                icon = "x" if report["errors"] else "ok"
                f.write(f"## Compile report ({icon}): {report['errorCount']} errors, "
                        f"{report['warningCount']} warnings\n\n```\n")
                with contextlib.redirect_stdout(f):
                    print_human_report(report, limit=args.limit)
                f.write("```\n")
        except OSError as exc:
            # A summary is a nicety; never fail the report over it.
            annotate("warning", f"Could not write summary to '{args.summary_file}': {exc}")

    if args.test:
        print_human_report(report, limit=args.limit)
    elif args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        out_path = os.path.join(args.out_dir, args.out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        if not args.quiet:
            print(f"Wrote {out_path}: {report['errorCount']} errors, "
                  f"{report['warningCount']} warnings "
                  f"(from {report['source']['primaryLog']})")
            for e in report["errors"][:10]:
                loc = f"{e['file']}({e['line']},{e['column']})" if e["file"] else "<no file>"
                print(f"  {loc}: {e['code']} [{e['hint']['kind']}] {e['message'][:120]}")
            if report["errorCount"] > 10:
                print(f"  ... and {report['errorCount'] - 10} more")
            if report["missingPackages"]:
                print(f"  possible missing packages: {', '.join(report['missingPackages'])}")
    else:
        json.dump(report, sys.stdout, indent=2)
        print()

    if not report["errors"] and not report["warnings"]:
        # A real log with 0 matches is suspicious -- format drift, wrong Unity
        # version, or the wrong file picked out of the bundle. Warn loudly
        # instead of looking identical to a genuinely clean compile.
        annotate("warning",
                 f"Parsed 0 errors and 0 warnings from {report['source']['linesRead']} log "
                 f"line(s) in '{report['source']['primaryLog']}'. If the build actually "
                 f"failed, DIAG_RE in tools/log_to_json.py may no longer match this Unity "
                 f"version's diagnostic format -- check the log manually.")

    if args.fail_on_error and report["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

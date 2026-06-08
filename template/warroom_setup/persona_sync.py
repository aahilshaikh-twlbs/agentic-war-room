"""Compile persona/ sources into SOUL.md + Claude head. Stdlib only, Python >=3.9.

Faithful port of aahil-sh's ops/scripts/aahil_sync.py with two additions:
  * {{placeholder}} substitution (from AgentIdentity) on target paths AND final content;
  * package-relative defaults for manifest + repo root.
Single source of truth = the persona/ overlay. Do not hand-edit generated outputs.
"""
import argparse
import difflib
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from .agent_model import AgentIdentity, load as load_identity


def strip_frontmatter_and_h1(text):
    # type: (str) -> str
    text = text.lstrip("\n")
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break
        else:
            raise ValueError("unclosed YAML frontmatter")
    while lines and lines[0].strip() == "":
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines.pop(0)
    return "\n".join(lines).strip("\n")


def strip_related(text):
    # type: (str) -> str
    lines = text.split("\n")
    out = []
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip() == "## Related":
            i += 1
            while i < n and not lines[i].startswith("## "):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip("\n")


def render_section(title, body):
    # type: (str, str) -> str
    return "## {0}\n\n{1}".format(title, body)


def _read(repo_root, rel):
    # type: (Path, str) -> str
    path = repo_root / rel
    if not path.is_file():
        raise FileNotFoundError("source file not found: {0}".format(path))
    return path.read_text(encoding="utf-8")


def _substitute(text, subs):
    # type: (str, Dict[str, str]) -> str
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def _render_output(entry, header, repo_root):
    # type: (dict, str, Path) -> str
    parts = [header]
    if entry.get("preamble"):
        parts.append(_read(repo_root, entry["preamble"]).rstrip())
    for sec in entry["sections"]:
        body = strip_related(strip_frontmatter_and_h1(_read(repo_root, sec["source"])))
        parts.append(render_section(sec["title"], body))
    if entry.get("trailer"):
        parts.append(_read(repo_root, entry["trailer"]).rstrip())
    return "\n\n".join(parts)


def run(manifest_path, repo_root, ident, check=False):
    # type: (Path, Path, AgentIdentity, bool) -> int
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    subs = ident.as_substitutions()
    header = manifest["header"]
    drift = 0
    for entry in manifest["outputs"]:
        content = _render_output(entry, header, Path(repo_root))
        content = _substitute(content, subs)
        if not content.endswith("\n"):
            content += "\n"
        target = Path(os.path.expanduser(_substitute(entry["target"], subs)))
        if check:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != content:
                drift += 1
                sys.stderr.write("DRIFT: {0}\n".format(target))
                sys.stderr.writelines(difflib.unified_diff(
                    current.splitlines(True), content.splitlines(True),
                    fromfile=str(target) + " (on disk)", tofile=str(target) + " (generated)"))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write (invariant I6): a crash must never leave a half-written
            # SOUL.md / Claude head, which would break agent startup.
            tmp = str(target) + ".tmp"
            Path(tmp).write_text(content, encoding="utf-8")
            os.replace(tmp, str(target))
            sys.stdout.write("wrote {0}\n".format(target))
    return 1 if (check and drift) else 0


def _default_paths():
    # type: () -> tuple
    # Package sits at <profile>/warroom_setup/. Manifest ships at <profile>/manifest.json.
    profile_root = Path(__file__).resolve().parents[1]
    return profile_root / "manifest.json", profile_root


def main(argv=None):
    # type: (Optional[list]) -> int
    default_manifest, default_root = _default_paths()
    ap = argparse.ArgumentParser(prog="persona_sync")
    ap.add_argument("--manifest", default=str(default_manifest))
    ap.add_argument("--repo-root", default=str(default_root))
    ap.add_argument("--agent-json", default=str(default_root / "local" / "agent.json"))
    ap.add_argument("--check", action="store_true", help="diff only, exit 1 on drift, never write")
    args = ap.parse_args(argv)
    ident = load_identity(Path(args.agent_json))
    if ident is None:
        sys.stderr.write("no agent identity at {0}; run `warroom setup` first\n".format(args.agent_json))
        return 2
    return run(Path(args.manifest), Path(args.repo_root), ident, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

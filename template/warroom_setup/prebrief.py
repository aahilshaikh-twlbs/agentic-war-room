"""Pre-brief pack operator surface. Stdlib only, Python >=3.9.

A pack is a trio: a bundle loader (skill-bundles/<pack>.yaml), member skills
(skills/<m>/SKILL.md), and a briefing/version-anchor doc
(shared/prebrief/<pack>.md). This module reads the doc, reports/verifies pack
integrity, (re)syncs the persona injection, pins via the user-owned local/
namespace, and posts an opt-in fleet nudge over the mailbox.

No new config keys (V-1 uses the local/ pin). No Hermes calls except the
best-effort `mailbox` shell-out in `announce`.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import enroll
from . import persona_sync
from .agent_model import load as load_identity

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def pack_doc_path(profile_root, pack):
    # type: (Path, str) -> Path
    return Path(profile_root) / "shared" / "prebrief" / ("%s.md" % pack)


def local_pin_path(profile_root, pack):
    # type: (Path, str) -> Path
    return Path(profile_root) / "local" / "prebrief" / ("%s.md" % pack)


def _frontmatter(text):
    # type: (str) -> str
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("pack doc missing YAML frontmatter")
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "\n".join(out)
        out.append(line)
    raise ValueError("unclosed pack-doc frontmatter")


def _scalar(fm, key):
    # type: (str, str) -> Optional[str]
    m = re.search(r"^%s:\s*(\S+)\s*$" % re.escape(key), fm, re.M)
    return m.group(1) if m else None


def _parse_doc_text(text):
    # type: (str) -> Dict
    fm = _frontmatter(text)
    pack = _scalar(fm, "pack")
    version = _scalar(fm, "pack_version")
    members = re.findall(r"^\s+-\s*([a-z][a-z0-9-]*)\s*$", fm, re.M)
    body_version = None
    m = re.search(r"^Pack version:\s*(\S+)\s*$", text, re.M)
    if m:
        body_version = m.group(1)
    return {"pack": pack, "pack_version": version, "members": members,
            "body_version": body_version}


def parse_pack(profile_root, pack):
    # type: (Path, str) -> Dict
    """Parse the pack doc (raises FileNotFoundError if absent)."""
    return _parse_doc_text(pack_doc_path(profile_root, pack).read_text(encoding="utf-8"))


def _bundle_skills(profile_root, pack):
    # type: (Path, str) -> List[str]
    bundle = Path(profile_root) / "skill-bundles" / ("%s.yaml" % pack)
    if not bundle.is_file():
        return []
    text = bundle.read_text(encoding="utf-8")
    m = re.search(r"^skills:\s*\n((?:\s+-\s*.*\n)+)", text, re.M)
    if not m:
        return []
    return re.findall(r"-\s*([a-z][a-z0-9-]*)", m.group(1))


def _member_installed(profile_root, member):
    # type: (Path, str) -> bool
    return (Path(profile_root) / "skills" / member / "SKILL.md").is_file()


def _pin_version(profile_root, pack):
    # type: (Path, str) -> Optional[str]
    pin = local_pin_path(profile_root, pack)
    if not pin.is_file():
        return None
    try:
        return _parse_doc_text(pin.read_text(encoding="utf-8")).get("pack_version")
    except ValueError:
        return None


def show(profile_root, pack="warroom", out=None):
    # type: (Path, str, object) -> int
    out = out if out is not None else sys.stdout
    try:
        info = parse_pack(profile_root, pack)
    except (FileNotFoundError, ValueError) as exc:
        out.write("no pack doc for %r: %s\n" % (pack, exc))
        return 1
    out.write("pack: %s\n" % info["pack"])
    out.write("version: %s\n" % info["pack_version"])
    pin = _pin_version(profile_root, pack)
    if pin is not None:
        out.write("pinned: %s (available: %s)\n" % (pin, info["pack_version"]))
    out.write("members:\n")
    for m in info["members"]:
        status = "installed" if _member_installed(profile_root, m) else "MISSING"
        out.write("  - %-20s %s\n" % (m, status))
    return 0


def verify(profile_root, pack="warroom", out=None):
    # type: (Path, str, object) -> int
    out = out if out is not None else sys.stdout
    doc = pack_doc_path(profile_root, pack)
    if not doc.is_file():
        out.write("FAIL: pack doc not found at %s\n" % doc)
        return 1
    try:
        info = _parse_doc_text(doc.read_text(encoding="utf-8"))
    except ValueError as exc:
        out.write("FAIL: %s\n" % exc)
        return 1
    problems = []  # type: List[str]
    if not info["pack_version"] or not _SEMVER.match(info["pack_version"]):
        problems.append("pack_version missing or not semver")
    if info["body_version"] is None:
        problems.append("body is missing the 'Pack version:' mirror line")
    elif info["body_version"] != info["pack_version"]:
        problems.append("version mirror drift: frontmatter %s != body %s"
                        % (info["pack_version"], info["body_version"]))
    for m in info["members"]:
        if not _member_installed(profile_root, m):
            problems.append("member %r does not resolve to skills/%s/SKILL.md" % (m, m))
    bundle_skills = set(_bundle_skills(profile_root, pack))
    members = set(info["members"])
    if bundle_skills != members:
        problems.append("bundle skills %s != pack members %s"
                        % (sorted(bundle_skills), sorted(members)))
    if problems:
        for p in problems:
            out.write("FAIL: %s\n" % p)
        return 1
    out.write("OK: pack %r v%s, %d members, bundle consistent\n"
              % (info["pack"], info["pack_version"], len(info["members"])))
    return 0


def _atomic_copy_text(src, dst, mode=0o600):
    # type: (Path, Path, int) -> None
    """Copy src -> dst atomically (temp + os.replace) under the same dir."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = Path(src).read_text(encoding="utf-8")
    tmp = str(dst) + ".tmp"
    try:
        Path(tmp).write_text(text, encoding="utf-8")
        try:
            os.chmod(tmp, mode)
        except OSError:
            pass
        os.replace(tmp, str(dst))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def pin(profile_root, pack="warroom", out=None):
    # type: (Path, str, object) -> int
    """Freeze the briefing: copy shared/prebrief/<pack>.md ->
    local/prebrief/<pack>.md (user-owned, survives `hermes profile update`).
    Atomic write. Returns 1 if the shared source is absent."""
    out = out if out is not None else sys.stdout
    src = pack_doc_path(profile_root, pack)
    if not src.is_file():
        out.write("cannot pin %r: no shared pack doc at %s\n" % (pack, src))
        return 1
    dst = local_pin_path(profile_root, pack)
    _atomic_copy_text(src, dst)
    out.write("pinned %r -> %s\n" % (pack, dst))
    return 0


def unpin(profile_root, pack="warroom", out=None):
    # type: (Path, str, object) -> int
    """Remove the local pin so the shared doc governs again. No-op (exit 0)
    when not pinned."""
    out = out if out is not None else sys.stdout
    dst = local_pin_path(profile_root, pack)
    if not dst.exists():
        out.write("%r not pinned (no %s)\n" % (pack, dst))
        return 0
    os.remove(str(dst))
    out.write("unpinned %r (removed %s)\n" % (pack, dst))
    return 0


def sync(profile_root, out=None):
    # type: (Path, object) -> int
    """Regenerate SOUL.md + the Claude head from the manifest (delegates to
    persona_sync.run). Returns 2 when no identity exists yet."""
    out = out if out is not None else sys.stdout
    profile_root = Path(profile_root)
    ident = load_identity(profile_root / "local" / "agent.json")
    if ident is None:
        out.write("no identity yet - run `warroom setup` first\n")
        return 2
    return persona_sync.run(profile_root / "manifest.json", profile_root,
                            ident, check=False)


_ANNOUNCE_SESSION = "warroom-prebrief-announce"


def announce(profile_root, pack="warroom", version=None, out=None, env=None):
    # type: (Path, str, Optional[str], object, Optional[dict]) -> int
    """Opt-in fleet nudge (P-2). Posts a board broadcast via the discovered
    mailbox CLI: 'pre-brief pack <pack> updated to v<ver>; restart to pick it
    up'. PULL semantics are unchanged — content still arrives via the next
    `hermes profile update` + session restart; this is only a soft signal.

    Fail-soft by contract: a missing CLI, a non-zero exit (e.g. no daemon / no
    session), an OSError, or a subprocess error (including a TimeoutExpired
    when a reachable-but-unresponsive daemon would otherwise hang the call)
    prints a warning and returns 1 WITHOUT raising. The send is bounded by a
    timeout so it never blocks the pack. The version defaults to the pack
    doc's pack_version.
    """
    out = out if out is not None else sys.stdout
    profile_root = Path(profile_root)
    ver = version
    if ver is None:
        try:
            ver = parse_pack(profile_root, pack).get("pack_version") or "?"
        except (FileNotFoundError, ValueError):
            ver = "?"
    cli = enroll.discover_mailbox_cli(env=env, repo_search_start=profile_root)
    if cli is None:
        out.write("announce: mailbox CLI not found; skipping fleet nudge "
                  "(content still arrives via `hermes profile update`)\n")
        return 1
    body = ("pre-brief pack %r updated to v%s; restart your session to pick it "
            "up (run `hermes profile update` first)" % (pack, ver))
    argv = [str(cli), "--session", _ANNOUNCE_SESSION, "send", "--to", "*",
            "--kind", "note", body]
    try:
        res = subprocess.run(argv, capture_output=True, text=True, env=env,
                             timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        out.write("announce: could not post nudge (%s)\n" % exc)
        return 1
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or "").strip()
        out.write("announce: mailbox send failed (%s); nudge not posted\n" % detail)
        return 1
    out.write("announce: posted pre-brief v%s nudge to the board\n" % ver)
    return 0

#!/usr/bin/env python3
"""Sanitization CI guard. Stdlib only, Python >=3.9.

Scans the shippable template tree for content that must never land in a public
distribution: org/employer artifacts that leak by SHAPE (Slack/Discord ids,
agent fingerprints, non-public hostnames, vault-style home paths) via
schema.BLOCKED_VALUES_REGEX, plus any configurable employer/operator NAME
substrings passed on the command line.

Usage:
    python3 scripts/sanitize_check.py [ROOT] [--name NAME [--name NAME ...]]

Exit 0 = clean, 1 = violations found (printed as path:line). The spec for this
check is documented in template/SANITIZATION.md.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DEFAULT = os.path.dirname(HERE)  # template/
if ROOT_DEFAULT not in sys.path:
    sys.path.insert(0, ROOT_DEFAULT)

from warroom_setup import schema  # noqa: E402

# Directories never scanned: dev/test/cache artifacts that legitimately contain
# shape-like fixtures (e.g. fake snowflakes in tests) or are not shipped.
EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", "tests", "node_modules",
}
# Files excluded because they DOCUMENT the patterns (and would self-match).
EXCLUDE_FILES = {"SANITIZATION.md", "sanitize_check.py", "schema.py"}
# Only scan text-ish files.
SCAN_SUFFIXES = {
    ".py", ".md", ".json", ".yaml", ".yml", ".sh", ".txt", ".cfg", ".toml",
    ".env", ".example", ".template",
}


def _iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for fn in filenames:
            if fn in EXCLUDE_FILES:
                continue
            suffix = os.path.splitext(fn)[1].lower()
            if suffix not in SCAN_SUFFIXES and not fn.startswith(".env"):
                continue
            yield os.path.join(dirpath, fn)


def scan(root, names=()):
    """Return a list of (path, lineno, reason, snippet) violations."""
    lowered = [n.lower() for n in names if n]
    violations = []
    for path in _iter_files(root):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            m = schema.BLOCKED_VALUES_REGEX.search(line)
            if m:
                violations.append((path, i, "blocked-shape", m.group(0)))
            low = line.lower()
            for n in lowered:
                if n in low:
                    violations.append((path, i, "blocked-name:%s" % n, n))
    return violations


def main(argv=None):
    p = argparse.ArgumentParser(prog="sanitize_check")
    p.add_argument("root", nargs="?", default=ROOT_DEFAULT)
    p.add_argument("--name", action="append", default=[],
                   help="employer/operator name substring to forbid (repeatable)")
    args = p.parse_args(argv)
    violations = scan(args.root, names=args.name)
    if not violations:
        print("sanitize_check: clean (%s)" % args.root)
        return 0
    for path, lineno, reason, snippet in violations:
        print("%s:%d: %s: %s" % (path, lineno, reason, snippet))
    print("sanitize_check: %d violation(s)" % len(violations))
    return 1


if __name__ == "__main__":
    sys.exit(main())

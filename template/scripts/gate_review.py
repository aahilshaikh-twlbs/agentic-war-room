#!/usr/bin/env python3
"""Failure-review CLI for the war-room confidence gate. Stdlib only, Py >=3.9.

Read-mostly operator tool for the classifier-tuning loop. It reads the hash-only
gate.log (0600, never the body), prints a decision-distribution table, and lets
the operator append a CONFIRMED failure to the JSON fixtures file by supplying
the ORIGINAL text transiently on stdin -- the tool re-hashes that text and
verifies it matches a log line's sha256 (proving the right message is labeled)
before writing only the labeled fixture row. It NEVER edits wg_classify.py and
NEVER writes the original text into the log.

Subcommands:
    review   --log <gate.log>                          print the distribution table
    label    --log <gate.log> --sha256 <hex>           hash-match an original (stdin)
             --expected claim|chatter --note <why>     + append a fixture row
             --fixtures <classifier_cases.json>

See docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import OrderedDict


def parse_line(line):
    """Parse one gate.log line into a dict, or None if it has no key=value pairs."""
    if not line or not line.strip():
        return None
    out = {}
    for tok in line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            out[k] = v
    if not out:
        return None
    return out


def read_log(path):
    """Return parsed dicts for every non-empty parseable line in the log file."""
    rows = []
    try:
        with open(str(path), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                d = parse_line(line)
                if d is not None:
                    rows.append(d)
    except OSError:
        return rows
    return rows


def _count(rows, key):
    counts = OrderedDict()
    for d in rows:
        v = d.get(key) or "(unset)"
        counts[v] = counts.get(v, 0) + 1
    return counts


def summarize(rows):
    """Distribution counts grouped by the review-relevant dimensions."""
    return {
        "total": len(rows),
        "verdict": _count(rows, "verdict"),
        "action": _count(rows, "action"),
        "reason": _count(rows, "reason"),
        "matched": _count(rows, "matched"),
    }


def _print_table(summary, out):
    out.write("gate.log review -- total: %d\n" % summary["total"])
    for dim in ("verdict", "action", "reason", "matched"):
        out.write("\n[%s]\n" % dim)
        for k, n in summary[dim].items():
            out.write("  %-16s %d\n" % (k, n))


def _cmd_review(args, out):
    _print_table(summarize(read_log(args.log)), out)
    return 0


def _atomic_write_text(path, text):
    """temp + os.replace, mirroring setup._atomic_write_text discipline."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _cmd_label(args, out, err, stdin):
    # The operator supplies the original text transiently; it is NEVER written to
    # the log. We hash it and confirm it matches A REAL LOG LINE being labeled --
    # the digest must equal both the operator-typed --sha256 AND the sha256 of an
    # actually-present gate.log line, proving the operator is labeling a message
    # that was really gated (spec Arch S3 / Reliability "operator mislabels").
    original = stdin.read()
    if original.endswith("\n"):
        original = original[:-1]
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if digest != args.sha256:
        err.write("sha256 mismatch: supplied text hashes to %s, not %s; "
                  "refusing to label the wrong message.\n" % (digest, args.sha256))
        return 3
    logged = {d.get("sha256") for d in read_log(args.log)}
    if digest not in logged:
        err.write("no gate.log line has sha256=%s; the supplied text was never "
                  "gated (or you read the wrong log). Refusing to label.\n" % digest)
        return 4
    rows = []
    if os.path.exists(args.fixtures):
        with open(args.fixtures, encoding="utf-8") as fh:
            rows = json.load(fh)
    rows.append({
        "text": original,
        "expected_is_claim": (args.expected == "claim"),
        "note": args.note,
    })
    _atomic_write_text(args.fixtures, json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    out.write("appended fixture (expected_is_claim=%s); SANITIZE before commit.\n"
              % (args.expected == "claim"))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="gate_review")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("review", help="print the gate.log distribution table")
    pr.add_argument("--log", required=True)

    pl = sub.add_parser("label", help="hash-match an original (stdin) + append a fixture")
    pl.add_argument("--log", required=True)
    pl.add_argument("--sha256", required=True, help="the log line's sha256 to match")
    pl.add_argument("--expected", required=True, choices=["claim", "chatter"])
    pl.add_argument("--note", required=True)
    pl.add_argument("--fixtures", required=True)

    args = p.parse_args(argv)
    if args.cmd == "review":
        return _cmd_review(args, sys.stdout)
    if args.cmd == "label":
        return _cmd_label(args, sys.stdout, sys.stderr, sys.stdin)
    return 2


if __name__ == "__main__":
    sys.exit(main())

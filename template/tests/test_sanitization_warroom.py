"""T9 — sanitization rules for the cross-agent mailbox routing block."""
import re
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1]
CONFIG = TEMPLATE / "config.yaml"
SANITIZE = TEMPLATE / "scripts" / "sanitize_check.py"

_MB_BEGIN = "# >>> warroom-mailbox >>>"
_MB_END = "# <<< warroom-mailbox <<<"


def _mailbox_label(text):
    m = re.search(r"^%s$(.*?)^%s$" % (re.escape(_MB_BEGIN), re.escape(_MB_END)),
                  text, re.MULTILINE | re.DOTALL)
    assert m, "shipped config.yaml must carry a mailbox: sentinel block"
    mm = re.search(r"^\s{2}label:\s*(.*)$", m.group(1), re.MULTILINE)
    assert mm, "mailbox block must declare a label"
    val = mm.group(1).strip()
    if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
        val = val[1:-1]
    return val


def test_shipped_template_mailbox_label_is_empty():
    assert _mailbox_label(CONFIG.read_text(encoding="utf-8")) == ""


def test_sanitize_check_flags_realname_label_in_fixture(tmp_path):
    root = tmp_path / "prof"
    root.mkdir()
    (root / "config.yaml").write_text(
        _MB_BEGIN + "\nmailbox:\n  board: shared\n  label: jane-doe\n" + _MB_END + "\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SANITIZE), str(root), "--name", "jane"],
        capture_output=True, text=True,
    )
    assert r.returncode == 1, r.stdout
    assert "jane" in r.stdout


def test_sanitize_check_passes_on_shipped_template():
    r = subprocess.run(
        # realistic operator/employer names that must not appear in the template
        [sys.executable, str(SANITIZE), str(TEMPLATE),
         "--name", "jane", "--name", "acme"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout

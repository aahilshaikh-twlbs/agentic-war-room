"""T10 -- installer sanitization + smoke regression (§10/K17/K21/F17)."""
import ast
import io
import re
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
TEMPLATE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = TEMPLATE_DIR / "scripts"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import awr_install as awr  # noqa: E402
import in_process_orchestrator as orch  # noqa: E402
import subprocess_runner as sr  # noqa: E402
from _substrate.discord_walkthrough import DiscordCreds  # noqa: E402

# Forbidden employer tokens, assembled from fragments so the contiguous literal
# never appears in this source file (the public-repo constraint applies here too)
# while the compiled regex still matches the real strings.
_E = "twelve"
_EMPLOYER_PATTERNS = [
    re.compile(_E + r"\s*labs", re.IGNORECASE),
    re.compile("@" + _E + "labs", re.IGNORECASE),
    re.compile("tl" + "-branding", re.IGNORECASE),
]

# Installer source files (NOT the vendored _substrate copies, which are scanned
# by the warroom_setup sanitization suite via byte-equality).
_INSTALLER_SOURCES = sorted(
    p for p in INSTALLER_DIR.glob("*.py")
) + [INSTALLER_DIR / "SMOKE.md", INSTALLER_DIR / "sync_substrate.sh"]

# Allowed top-level import roots for installer modules.
_STDLIB = {
    "argparse", "os", "sys", "subprocess", "signal", "threading", "time",
    "collections", "dataclasses", "pathlib", "typing", "types", "uuid", "json",
    "stat", "shutil", "re", "tempfile", "filecmp", "io", "__future__",
}
_INSTALLER_LOCAL = {
    "precheck", "subprocess_runner", "progress", "masked_prompt",
    "profile_detect", "sidecar_state", "rollback", "in_process_orchestrator",
    "awr_install", "_substrate",
}


def test_no_employer_strings():
    offenders = []
    for path in _INSTALLER_SOURCES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in _EMPLOYER_PATTERNS:
            if pat.search(text):
                offenders.append("%s ~ %s" % (path.name, pat.pattern))
    assert not offenders, offenders


def test_smoke_uses_neutral_handles():
    smoke = (INSTALLER_DIR / "SMOKE.md").read_text(encoding="utf-8")
    assert "alpha-sh" in smoke
    assert "beta-sh" in smoke
    assert "shared" in smoke
    for pat in _EMPLOYER_PATTERNS:
        assert not pat.search(smoke)


def test_install_log_redacts_secrets(tmp_path):
    # Run the orchestrator with real secrets and assert install.log never
    # captures their values.
    secret_key = "sk-ant-" + "Z" * 40
    secret_tok = "SECRETTOKEN_NOT_REAL.zzzzz.SECRETTOKEN_NOT_REAL"
    answers = awr.InstallerAnswers(
        source="/tmpl", profile_name="alpha-sh", channels={"discord"},
        discord_creds=DiscordCreds(bot_token=secret_tok, channel_id="12345678901234567"),
        slack_creds=None, anthropic_key=secret_key, agent_name="alpha-sh",
        display_name="Alpha", handle="alpha-sh", discord_allowed_users=["u1"],
        min_confidence=80, model="opus", board="shared", label="alpha-sh",
    )
    import warroom_setup.agent_model as am
    import warroom_setup.enroll as en
    import warroom_setup.setup as st
    from types import SimpleNamespace

    orch.execute(
        answers, profiles_root=tmp_path,
        hermes_runner=lambda c, *, timeout, tee=None: sr.CommandResult(0, ["installed ok"], 0.1),
        plugin_runner=lambda c, *, timeout, tee=None: sr.CommandResult(0, ["enabled"], 0.1),
        importer=lambda pr: SimpleNamespace(setup=st, agent_model=am, enroll=en),
        out=io.StringIO(),
    )
    log = (tmp_path / "alpha-sh" / "local" / "install.log").read_text(encoding="utf-8")
    assert secret_key not in log
    assert secret_tok not in log


def test_sanitize_check_walks_installer():
    import sanitize_check

    files = list(sanitize_check._iter_files(str(TEMPLATE_DIR)))
    rels = {str(Path(f).relative_to(TEMPLATE_DIR)) for f in files}
    assert "scripts/installer/awr_install.py" in rels
    assert "scripts/installer/SMOKE.md" in rels
    # and a real run over the whole template stays clean
    assert sanitize_check.scan(str(TEMPLATE_DIR)) == []


def test_imports_only_substrate_and_stdlib():
    offenders = []
    for path in INSTALLER_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:  # MODULE-LEVEL imports only
            roots = []
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots = [node.module.split(".")[0]]
            for root in roots:
                assert root != "warroom_setup", (
                    "%s imports warroom_setup at module level" % path.name
                )
                if root not in _STDLIB and root not in _INSTALLER_LOCAL:
                    offenders.append("%s: %s" % (path.name, root))
    assert not offenders, offenders

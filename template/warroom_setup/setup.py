"""Setup orchestration. Stdlib only, Python >=3.9.

run_setup(profile_root): seed the user-owned overlay (local/persona, local/agent.json),
collect identity/toggles/secrets, write .env, patch the war_room block in config.yaml,
compile the persona via persona_sync, and persist non-secret answers.
"""
import os
import re
import shutil
import stat
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set

from . import answers as answers_mod
from . import persona_sync, prompts, render, schema, selectables, validators
from .agent_model import AgentIdentity
from .agent_model import load as load_identity
from .agent_model import save as save_identity


# Validators now live in validators.py (single source of truth). Kept as a
# module-level alias for backward compatibility with callers/tests that import
# setup._validate_slug.
_validate_slug = validators.valid_slug


def _slugify(s):
    # type: (str) -> str
    return re.sub(r"[^a-z0-9-]", "-", (s or "").lower()).strip("-") or "warroom"


def _secure_file(path):
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def _secure_dir(path):
    try:
        os.chmod(str(path), 0o700)
    except OSError:
        pass


_WR_BEGIN = "# >>> warroom-managed (set via `warroom setup`) >>>"
_WR_END = "# <<< warroom-managed <<<"

_MB_BEGIN = "# >>> warroom-mailbox >>>"
_MB_END = "# <<< warroom-mailbox <<<"


def _replace_sentinel_block(text, begin, end, new_body, yaml_key=None):
    # type: (str, str, str, str, Optional[str]) -> str
    """Replace the region delimited by the `begin`/`end` sentinel LINES with
    `new_body` (which itself includes the begin/end lines), else append it.

    Uses an anchored regex (`^begin$ ... ^end$`, MULTILINE|DOTALL) so a sentinel
    string embedded mid-line in some other block's body is NOT matched — only a
    bare sentinel line on its own. Surrounding text is preserved verbatim.

    Fallback: if the sentinels are absent AND `yaml_key` is supplied, re-anchor
    onto the bare top-level key span (`^<key>:` line plus its indented/blank
    continuation lines, up to the next top-level key or EOF) and replace that.
    This re-sentinels a YAML block whose comments were stripped by a PyYAML
    re-emit, so a subsequent patch never duplicates `war_room:`/`mailbox:`.
    The bare header is anchored (`^key:[ \\t]*\\n`) so `mailboxes_other:` does
    not match `mailbox`. Blank lines that trailed the bare span are preserved as
    the separator to the next key (else the new block would butt against it).
    Replacement is spliced by string slicing (not `re.sub`) to avoid backref
    interpretation of `\\g`/`\\1` sequences in `new_body`.
    """
    pattern = re.compile(
        r"^%s$.*?^%s$" % (re.escape(begin), re.escape(end)),
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(lambda _m: new_body, text)
    if yaml_key:
        bare = re.compile(
            r"(?m)^%s:[ \t]*\n(?:[ \t].*\n|[ \t]*\n)*" % re.escape(yaml_key)
        )
        m = bare.search(text)
        if m:
            matched = m.group(0)
            # Newlines trailing the last content line (>=1) belong between
            # blocks; re-emit them so the separator to the next key survives.
            trailing = len(matched) - len(matched.rstrip("\n"))
            replacement = new_body + ("\n" * trailing if trailing else "\n")
            replaced = text[:m.start()] + replacement + text[m.end():]
            return replaced if replaced.endswith("\n") else replaced + "\n"
    if text.strip():
        return text.rstrip("\n") + "\n\n" + new_body + "\n"
    return new_body + "\n"


def _atomic_write_text(path, text):
    # type: (Path, str) -> None
    """Write `text` to `path` atomically (tempfile in same dir + os.replace).
    SIGTERM mid-write leaves the original intact. Best-effort tmp cleanup."""
    path = Path(path)
    tmp = str(path) + ".tmp"
    try:
        Path(tmp).write_text(text, encoding="utf-8")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, str(path))


# Percentage clamp now lives in schema.py (single source of truth). Kept as a
# module-level alias for backward compatibility with callers/tests.
_clamp_pct = schema.clamp_pct


def seed_overlay(profile_root):
    # type: (Path) -> None
    """Copy shipped persona/ skeleton into the user-owned local/persona/ overlay
    ONLY for files that do not yet exist (never clobber user edits). local/ is in
    Hermes' USER_OWNED_EXCLUDE so it survives `hermes profile update`."""
    src = profile_root / "persona"
    dst = profile_root / "local" / "persona"
    dst.mkdir(parents=True, exist_ok=True)
    _secure_dir(profile_root / "local")
    for f in sorted(src.glob("*.md")):
        target = dst / f.name
        if not target.exists():
            shutil.copy2(f, target)


def write_env(profile_root, env_values, filename=".env"):
    # type: (Path, Dict[str, str], str) -> None
    """Write an env file by overlaying provided values onto the base file's keys.
    Keys not in the base are appended. Existing values are overwritten for provided
    keys, preserved otherwise.

    filename selects the target relative to profile_root (default ".env"). Only the
    canonical .env is seeded from .env.EXAMPLE; a custom filename (e.g.
    "local/sentinel.env") starts from its own existing contents or empty, and its
    parent dirs are created as needed."""
    profile_root = Path(profile_root)
    example = profile_root / ".env.EXAMPLE"
    env_path = profile_root / filename
    base_lines = []
    if env_path.exists():
        base_lines = env_path.read_text(encoding="utf-8").splitlines()
    elif filename == ".env" and example.exists():
        base_lines = example.read_text(encoding="utf-8").splitlines()
    seen = set()  # type: Set[str]
    out = []
    for line in base_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in env_values:
                out.append("%s=%s" % (key, env_values[key]))
                seen.add(key)
                continue
        out.append(line)
    for key, val in env_values.items():
        if key not in seen:
            out.append("%s=%s" % (key, val))
    env_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(env_path) + ".tmp"
    Path(tmp).write_text("\n".join(out) + "\n", encoding="utf-8")
    os.replace(tmp, str(env_path))
    _secure_file(env_path)


def _yaml_scalar(v):
    # type: (object) -> str
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def patch_war_room_block(profile_root, board=None, **overrides):
    # type: (Path, object, object) -> None
    """Idempotently write the sentinel-managed war_room block (update in place if
    present, else append). Line-based, no YAML dependency.

    Defaults are sourced from schema.DEFAULTS; any key in schema.WAR_ROOM_KEYS may
    be passed as a kwarg (label, role, enabled, gate_action, ...). The legacy
    (board, min_confidence=, gate_action=, enforce=, show_confidence_badge=)
    calling convention is preserved unchanged. Empty-string values are omitted so
    the rendered block stays clean; board falls back to "default" when blank.
    """
    unknown = set(overrides) - set(schema.WAR_ROOM_KEYS)
    if unknown:
        raise TypeError(
            "patch_war_room_block() got unexpected war_room keys: %s"
            % ", ".join(sorted(unknown))
        )

    values = dict(schema.DEFAULTS)
    values.update(overrides)
    if board is not None:
        values["board"] = board
    values["board"] = (values.get("board") or "default")
    values["min_confidence"] = schema.clamp_pct(values.get("min_confidence"))

    cfg = Path(profile_root) / "config.yaml"
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""

    lines = [_WR_BEGIN, "war_room:"]
    for key in schema.WAR_ROOM_KEYS:
        val = values.get(key)
        if val is None or (isinstance(val, str) and val == ""):
            continue
        lines.append("  %s: %s" % (key, _yaml_scalar(val)))
    lines.append(_WR_END)
    block = "\n".join(lines)

    new = _replace_sentinel_block(text, _WR_BEGIN, _WR_END, block, yaml_key="war_room")
    _atomic_write_text(cfg, new)


def patch_mailbox_block(profile_root, **overrides):
    # type: (Path, object) -> None
    """Idempotently write the sentinel-managed top-level `mailbox:` routing block
    (locked decision #1: routing lives in config.yaml). Mirrors
    patch_war_room_block but uses the distinct `# >>> warroom-mailbox >>>` pair
    and the hardened anchored-regex replacer. All four MAILBOX_KEYS are always
    rendered (empty values shown as `key: ""`) so the shipped template carries an
    explicit empty `label`. Atomic write via tempfile + os.replace.
    """
    unknown = set(overrides) - set(schema.MAILBOX_KEYS)
    if unknown:
        raise TypeError(
            "patch_mailbox_block() got unexpected mailbox keys: %s"
            % ", ".join(sorted(unknown))
        )
    values = dict(schema.MAILBOX_DEFAULTS)
    values.update(overrides)
    values["board"] = (values.get("board") or "default")

    cfg = Path(profile_root) / "config.yaml"
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""

    lines = [_MB_BEGIN, "mailbox:"]
    for key in schema.MAILBOX_KEYS:
        val = values.get(key, "")
        if isinstance(val, str) and val == "":
            lines.append('  %s: ""' % key)
        else:
            lines.append("  %s: %s" % (key, _yaml_scalar(val)))
    lines.append(_MB_END)
    block = "\n".join(lines)

    new = _replace_sentinel_block(text, _MB_BEGIN, _MB_END, block, yaml_key="mailbox")
    _atomic_write_text(cfg, new)


# Matches the `- command: "bash <...>first_run.sh"` line under hooks.on_session_start.
# Hermes runs hooks with shell=False + arbitrary cwd and does NO {{PROFILE_ROOT}}
# substitution, so the command must carry an absolute path. This rewriter is run
# at install time (by enroll.bootstrap) to convert the shipped relative command
# into an absolute one. Idempotent.
_HOOK_CMD_RE = re.compile(
    r'^(?P<pre>\s*-\s*command:\s*")bash\s+\S*?first_run\.sh(?P<post>"\s*)$',
    re.MULTILINE,
)


def patch_hooks_command(profile_root):
    # type: (Path) -> bool
    """Rewrite hooks.on_session_start[*].command to an absolute
    `bash <profile_root>/hooks/first_run.sh`. Idempotent; atomic write. Returns
    True iff config.yaml changed. No-op (returns False) if config.yaml is absent
    or the command line isn't present."""
    profile_root = Path(profile_root)
    cfg = profile_root / "config.yaml"
    if not cfg.exists():
        return False
    text = cfg.read_text(encoding="utf-8")
    abs_cmd = "bash %s" % (profile_root / "hooks" / "first_run.sh")

    def _sub(m):
        return "%sbash %s%s" % (m.group("pre"), profile_root / "hooks" / "first_run.sh", m.group("post"))

    new = _HOOK_CMD_RE.sub(_sub, text)
    if new == text:
        return False
    tmp = str(cfg) + ".tmp"
    Path(tmp).write_text(new, encoding="utf-8")
    os.replace(tmp, str(cfg))
    return True


_WARROOM_PERSONA_RULE = (
    "- Before editing a file a board peer may also be touching, run "
    "`mailbox claim-lane <lane>` to coordinate. Release with "
    "`mailbox release-lane <lane>` when done."
)

_PERSONA_SENTINEL_ABBR = {"warroom": "WR"}


def _persona_sentinels(sentinel_id):
    # type: (str) -> tuple
    abbr = _PERSONA_SENTINEL_ABBR.get(sentinel_id)
    if abbr is None:
        abbr = re.sub(r"[^A-Za-z0-9]+", "_", str(sentinel_id)).strip("_").upper() or "WR"
    return ("<!-- _%s_PERSONA_BEGIN -->" % abbr, "<!-- _%s_PERSONA_END -->" % abbr)


def patch_persona_decisions(profile_root, rule_text, sentinel_id="warroom"):
    # type: (Path, str, str) -> bool
    """Accumulate a persona rule into the sentinel-managed region of the
    user-owned local/persona/decisions.md overlay.

    Unlike patch_war_room_block (full replace), this APPENDS rule_text inside
    the region and never clobbers existing content -- so owner hand-edits made
    between the sentinels survive. Idempotent: a rule already present in the
    region is a no-op. Returns True iff the file changed.
    """
    begin, end = _persona_sentinels(sentinel_id)
    rule = (rule_text or "").strip()
    target = Path(profile_root) / "local" / "persona" / "decisions.md"
    text = target.read_text(encoding="utf-8") if target.exists() else ""

    if begin in text and end in text:
        head, rest = text.split(begin, 1)
        region, tail = rest.split(end, 1)
        if rule and rule in region:
            return False  # idempotent no-op
        new_region = region.rstrip("\n") + ("\n" + rule if rule else "") + "\n"
        new = head + begin + "\n" + new_region.lstrip("\n") + end + tail
    else:
        block = "\n".join([begin, rule, end]) if rule else "\n".join([begin, end])
        new = (text.rstrip("\n") + "\n\n" + block + "\n") if text.strip() else (block + "\n")

    if new == text:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new, encoding="utf-8")
    return True


def _resolve_toggles(profile_root, yes, reconfigure, toggle_in_stream, out_stream):
    # type: (Path, bool, bool, object, object) -> Set[str]
    """ccpkg precedence ladder adapted: reconfigure&tty -> wizard; profile -> replay;
    tty&no-profile -> wizard; else defaults."""
    stages = selectables.build_stages(selectables.TOGGLES)
    defaults = selectables.default_ids(selectables.TOGGLES)
    prior = answers_mod.load(profile_root / "local" / answers_mod.FILENAME)

    def replay(ans):
        return set(ans.selected) | (defaults - set(ans.deselected))

    is_tty = (not yes) and render._is_tty(toggle_in_stream)
    if reconfigure and is_tty:
        pre = replay(prior) if prior else set(defaults)
        return set(render.run_wizard(stages, pre, in_stream=toggle_in_stream, out_stream=out_stream))
    if prior is not None:
        return replay(prior)
    if is_tty:
        return set(render.run_wizard(stages, set(defaults), in_stream=toggle_in_stream, out_stream=out_stream))
    # headless first run: in numbered-fallback path run_wizard still consumes the stream;
    # if not a tty and no prior answers, fall to defaults.
    if not yes:
        return set(render.run_wizard(stages, set(defaults), in_stream=toggle_in_stream, out_stream=out_stream))
    return set(defaults)


def run_setup(profile_root, yes=False, reconfigure=False, sync_only=False,
              in_stream=None, out_stream=None, toggle_in_stream=None):
    # type: (Path, bool, bool, bool, object, object, object) -> int
    profile_root = Path(profile_root)
    out_stream = out_stream if out_stream is not None else sys.stdout
    in_stream = in_stream if in_stream is not None else sys.stdin
    toggle_in_stream = toggle_in_stream if toggle_in_stream is not None else in_stream

    seed_overlay(profile_root)
    agent_json = profile_root / "local" / "agent.json"

    if sync_only:
        ident = load_identity(agent_json)
        if ident is None:
            out_stream.write("no identity yet - run `warroom setup` first\n")
            return 2
        return persona_sync.run(profile_root / "manifest.json", profile_root, ident, check=False)

    selected = _resolve_toggles(profile_root, yes, reconfigure, toggle_in_stream, out_stream)

    # Collect free-text + secrets (skip in pure headless replay when identity already exists).
    prior_ident = load_identity(agent_json)
    if yes and prior_ident is not None:
        values = {}  # type: Dict[str, str]
        ident = prior_ident
    else:
        values = prompts.collect(selectables.TEXT_FIELDS, selected,
                                 in_stream=in_stream, out_stream=out_stream)
        agent_name = values.get("agent_name", "").strip() or (prior_ident.agent_name if prior_ident else "warroom")
        handle = values.get("handle", "").strip() or agent_name
        display = values.get("display_name", "").strip() or agent_name
        if not validators.valid_slug(agent_name):
            out_stream.write("  agent_name %r invalid (need ^[a-z][a-z0-9-]*$); slugifying\n" % agent_name)
            agent_name = _slugify(agent_name)
        if not validators.valid_handle(handle):
            handle = agent_name
        model = "sonnet" if "model.sonnet" in selected and "model.opus" not in selected else "opus"
        fingerprint = prior_ident.agent_fingerprint if prior_ident else "%s-%s" % (agent_name, uuid.uuid4().hex[:12])
        ident = AgentIdentity(agent_name=agent_name, handle=handle, display_name=display,
                              model=model, specialist_prefix=agent_name, agent_fingerprint=fingerprint)
    save_identity(agent_json, ident)

    # .env: only env-mapped values.
    env_values = {k: v for k, v in values.items() if k in selectables.ENV_FIELD_IDS and v}
    if env_values:
        write_env(profile_root, env_values, filename=".env")

    if "warroom.enroll" in selected:
        mc = schema.clamp_pct(values.get("warroom.min_confidence", ""))
        board = values.get("warroom.board", "").strip()
        parent = values.get("warroom.parent", "").strip()
        patch_war_room_block(profile_root, board, parent=parent,
                             min_confidence=mc, enforce=("warroom.enforce" in selected))
        # Cross-agent runtime: bootstrap writes the mailbox: block (same board,
        # keeping war_room.board / mailbox.board in sync per decision #13),
        # persists runtime state, and installs the Claude Code SessionStart hook.
        label = values.get("warroom.label", "").strip() or ident.handle
        from . import enroll
        # parent kwarg only when supplied: keeps monkeypatched legacy-signature
        # bootstrap recorders (existing tests) working unchanged.
        if parent:
            st = enroll.bootstrap(profile_root, board, label, parent=parent)
        else:
            st = enroll.bootstrap(profile_root, board, label)
        # Teach the persona to use mailbox lane-claims ambiently (idempotent).
        patch_persona_decisions(profile_root, _WARROOM_PERSONA_RULE,
                                sentinel_id="warroom-runtime")
        if st.status != "ok":
            out_stream.write(
                'war-room: mailbox CLI not found — see template/README.md '
                '"Installing the mailbox runtime" to activate cross-agent features.\n'
            )

    # Persist non-secret answers (deselected = default-on ids that ended up off).
    all_default = selectables.default_ids(selectables.TOGGLES)
    deselected = sorted((all_default | selected) - selected)
    persist_values = {k: v for k, v in values.items() if k not in selectables.SECRET_IDS}
    answers_mod.save(profile_root / "local" / answers_mod.FILENAME,
                     answers_mod.Answers(selected=sorted(selected), deselected=deselected, values=persist_values))

    rc = persona_sync.run(profile_root / "manifest.json", profile_root, ident, check=False)
    out_stream.write("\nSetup complete. Next:\n"
                     "  cp .env.EXAMPLE .env   # if you skipped any tokens, fill them now\n"
                     "  hermes -p %s gateway install && hermes -p %s gateway restart\n"
                     % (ident.handle, ident.handle))
    return rc

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
from . import persona_sync, prompts, render, selectables
from .agent_model import AgentIdentity
from .agent_model import load as load_identity
from .agent_model import save as save_identity


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def _validate_slug(s):
    # type: (str) -> bool
    return bool(_SLUG_RE.match(s or ""))


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


def write_env(profile_root, env_values):
    # type: (Path, Dict[str, str]) -> None
    """Write .env by overlaying provided values onto .env.EXAMPLE keys. Keys not in
    the example are appended. Existing .env values are overwritten for provided keys,
    preserved otherwise."""
    example = profile_root / ".env.EXAMPLE"
    env_path = profile_root / ".env"
    base_lines = []
    if env_path.exists():
        base_lines = env_path.read_text(encoding="utf-8").splitlines()
    elif example.exists():
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
    tmp = str(env_path) + ".tmp"
    Path(tmp).write_text("\n".join(out) + "\n", encoding="utf-8")
    os.replace(tmp, str(env_path))
    _secure_file(env_path)


def patch_war_room_block(profile_root, board):
    # type: (Path, str) -> None
    """Append/replace a top-level `war_room:` block in config.yaml. Minimal line-based
    edit (no YAML dep): if a war_room: block exists, leave it; else append one."""
    cfg = profile_root / "config.yaml"
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if "\nwar_room:" in ("\n" + text):
        return
    block = "\nwar_room:\n  enabled: true\n  board: %s\n  role: contributor\n" % (board or "default")
    cfg.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")


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
        if not _validate_slug(agent_name):
            out_stream.write("  agent_name %r invalid (need ^[a-z][a-z0-9-]*$); slugifying\n" % agent_name)
            agent_name = _slugify(agent_name)
        if not _validate_slug(handle):
            handle = agent_name
        model = "sonnet" if "model.sonnet" in selected and "model.opus" not in selected else "opus"
        fingerprint = prior_ident.agent_fingerprint if prior_ident else "%s-%s" % (agent_name, uuid.uuid4().hex[:12])
        ident = AgentIdentity(agent_name=agent_name, handle=handle, display_name=display,
                              model=model, specialist_prefix=agent_name, agent_fingerprint=fingerprint)
    save_identity(agent_json, ident)

    # .env: only env-mapped values.
    env_values = {k: v for k, v in values.items() if k in selectables.ENV_FIELD_IDS and v}
    if env_values:
        write_env(profile_root, env_values)

    if "warroom.enroll" in selected:
        patch_war_room_block(profile_root, values.get("warroom.board", "").strip())

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

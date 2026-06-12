"""Pre-brief pack integration smoke (spec design.md:528-538).

Gated: @integration + --runintegration (mirrors test_installer_e2e.py). The
`hermes profile install`/`update` copy is SIMULATED by reproducing the verified
_copy_dist_payload contract (catch-all staged.iterdir() copy; skip
USER_OWNED_EXCLUDE incl. `local`; preserve config.yaml on update) — see
VERIFY-AGAINST-HERMES #2 and profile_distribution.py:560-570. A real Hermes
cannot be imported under the 3.9 template .venv (Hermes needs 3.10+).

Run: template/.venv/bin/python -m pytest tests/test_prebrief_e2e.py --runintegration -q
"""
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

TEMPLATE = Path(__file__).resolve().parents[1]
if str(TEMPLATE) not in sys.path:
    sys.path.insert(0, str(TEMPLATE))

from warroom_setup import prebrief  # noqa: E402

# The verified USER_OWNED_EXCLUDE subset that matters for a pack update: `local`
# is preserved (pins survive); config.yaml is preserved on update. Mirrors
# profile_distribution.USER_OWNED_EXCLUDE (`local` at :118) + the preserve-config
# branch (:568-570).
_USER_OWNED_EXCLUDE = {"local", "memories", "sessions", "logs", "plans",
                       "workspace", "home", "cron"}


def _copy_dist_payload(staged, target, *, preserve_config):
    """Faithful re-impl of the verified Hermes catch-all copy loop.

    Copies every top-level entry from `staged` into `target` EXCEPT names in
    USER_OWNED_EXCLUDE; preserves an existing config.yaml when preserve_config.
    """
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(staged.iterdir()):
        name = entry.name
        if name in _USER_OWNED_EXCLUDE:
            continue
        if name == "config.yaml" and preserve_config and (target / "config.yaml").exists():
            continue
        dest = target / name
        if entry.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(entry, dest,
                            ignore=lambda d, names: [n for n in names if n in _USER_OWNED_EXCLUDE])
        else:
            shutil.copy2(entry, dest)


def _stage_from_template(staged):
    """Build a staged distribution carrying the pack trio + config.yaml."""
    staged.mkdir(parents=True, exist_ok=True)
    for d in ("skill-bundles", "shared", "skills"):
        shutil.copytree(TEMPLATE / d, staged / d)
    shutil.copy2(TEMPLATE / "config.yaml", staged / "config.yaml")
    return staged


def _install(staged, target):
    _copy_dist_payload(staged, target, preserve_config=False)


def _update(staged, target):
    _copy_dist_payload(staged, target, preserve_config=True)


# --------------------------------------------------------------------------- #
# (1) install lands the trio
# --------------------------------------------------------------------------- #
def test_install_lands_pack_trio(tmp_path):
    staged = _stage_from_template(tmp_path / "staged")
    target = tmp_path / "profile"
    _install(staged, target)
    assert (target / "skill-bundles" / "warroom.yaml").is_file()
    assert (target / "shared" / "prebrief" / "warroom.md").is_file()
    members = prebrief.parse_pack(target, "warroom")["members"]
    assert members == ["confidence-gate", "warroom"]
    for m in members:
        assert (target / "skills" / m / "SKILL.md").is_file()


# --------------------------------------------------------------------------- #
# (2) the loader exposes /<pack> and its skills resolve to bodies
# --------------------------------------------------------------------------- #
def test_installed_bundle_loads_member_bodies(tmp_path):
    staged = _stage_from_template(tmp_path / "staged")
    target = tmp_path / "profile"
    _install(staged, target)
    # `bundles list` would show /warroom because the loader file is at the
    # scanned path <profile>/skill-bundles/warroom.yaml (VERIFY-AGAINST-HERMES #3).
    assert (target / "skill-bundles" / "warroom.yaml").is_file()
    # invoking /warroom loads member bodies -> each member resolves to a body.
    assert prebrief.verify(target, "warroom") == 0  # bundle skills == members, bodies present


# --------------------------------------------------------------------------- #
# (3) bump + update REPLACES the pack, PRESERVES config.yaml + local/
# --------------------------------------------------------------------------- #
def test_update_replaces_pack_and_preserves_config_and_local(tmp_path):
    staged = _stage_from_template(tmp_path / "staged")
    target = tmp_path / "profile"
    _install(staged, target)

    # operator owns config.yaml + a local/ overlay
    (target / "config.yaml").write_text("OPERATOR EDITED CONFIG\n", encoding="utf-8")
    (target / "local").mkdir(parents=True, exist_ok=True)
    (target / "local" / "keepme.txt").write_text("operator data\n", encoding="utf-8")

    # bump pack_version in the staged distribution (the upstream change)
    doc = staged / "shared" / "prebrief" / "warroom.md"
    bumped = doc.read_text(encoding="utf-8").replace(
        "pack_version: 1.0.0", "pack_version: 1.1.0").replace(
        "Pack version: 1.0.0", "Pack version: 1.1.0")
    doc.write_text(bumped, encoding="utf-8")

    _update(staged, target)

    # pack doc + bundle + skills were REPLACED (new version present)
    assert prebrief.parse_pack(target, "warroom")["pack_version"] == "1.1.0"
    assert (target / "skill-bundles" / "warroom.yaml").is_file()
    for m in ("confidence-gate", "warroom"):
        assert (target / "skills" / m / "SKILL.md").is_file()
    # config.yaml + local/ were PRESERVED (operator content intact)
    assert (target / "config.yaml").read_text(encoding="utf-8") == "OPERATOR EDITED CONFIG\n"
    assert (target / "local" / "keepme.txt").read_text(encoding="utf-8") == "operator data\n"


# --------------------------------------------------------------------------- #
# (4) a local/prebrief/<pack>.md pin SURVIVES update
# --------------------------------------------------------------------------- #
def test_pin_survives_update(tmp_path):
    staged = _stage_from_template(tmp_path / "staged")
    target = tmp_path / "profile"
    _install(staged, target)

    # operator pins the briefing at v1.0.0
    assert prebrief.pin(target, "warroom") == 0
    pin = target / "local" / "prebrief" / "warroom.md"
    pinned_before = pin.read_text(encoding="utf-8")
    assert "pack_version: 1.0.0" in pinned_before

    # upstream bumps to 1.1.0 and the operator updates
    doc = staged / "shared" / "prebrief" / "warroom.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace(
        "pack_version: 1.0.0", "pack_version: 1.1.0").replace(
        "Pack version: 1.0.0", "Pack version: 1.1.0"), encoding="utf-8")
    _update(staged, target)

    # the pin SURVIVED (local/ is user-owned) and still reads 1.0.0,
    # while the shared doc now reads 1.1.0 -> show reports the gap.
    assert pin.is_file()
    assert pin.read_text(encoding="utf-8") == pinned_before
    assert prebrief.parse_pack(target, "warroom")["pack_version"] == "1.1.0"

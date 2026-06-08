"""T4 -- existing-profile detection + collision strategy (§8)."""
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import profile_detect as pd  # noqa: E402


def _hermes_profile(root, *, warroom=True, user_data=False):
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text("name: alpha-sh\n", encoding="utf-8")
    if warroom:
        ws = root / "warroom_setup"
        ws.mkdir()
        (ws / "__init__.py").write_text("", encoding="utf-8")
    if user_data:
        local = root / "local"
        local.mkdir()
        (local / "agent.json").write_text("{}", encoding="utf-8")
    return root


def test_reports_missing(tmp_path):
    insp = pd.inspect_profile(tmp_path / "nope")
    assert insp.exists is False
    assert insp.strategy == pd.PROCEED


def test_detects_hermes_via_config_yaml(tmp_path):
    root = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=False)
    insp = pd.inspect_profile(root)
    assert insp.is_hermes_managed is True
    assert insp.has_warroom_setup is True
    assert insp.strategy == pd.PROCEED  # hermes+warroom, no user data


def test_detects_legacy_hermes(tmp_path):
    # Legacy Hermes profile: config.yaml present but NO distribution.yaml and no
    # warroom_setup -> a different distribution -> abort.
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "config.yaml").write_text("name: legacy\n", encoding="utf-8")
    insp = pd.inspect_profile(root)
    assert insp.is_hermes_managed is True
    assert insp.has_warroom_setup is False
    assert insp.strategy == pd.ABORT


def test_detects_user_data(tmp_path):
    root = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=True)
    insp = pd.inspect_profile(root)
    assert insp.has_user_data is True
    assert insp.strategy == pd.RECONFIGURE
    # also via persona dir
    root2 = _hermes_profile(tmp_path / "beta-sh", warroom=True, user_data=False)
    persona = root2 / "local" / "persona"
    persona.mkdir(parents=True)
    (persona / "p.json").write_text("{}", encoding="utf-8")
    assert pd.inspect_profile(root2).has_user_data is True


def test_reports_warroom_setup_presence(tmp_path):
    with_ws = _hermes_profile(tmp_path / "withws", warroom=True)
    without_ws = _hermes_profile(tmp_path / "nows", warroom=False)
    assert pd.inspect_profile(with_ws).has_warroom_setup is True
    assert pd.inspect_profile(without_ws).has_warroom_setup is False


def test_strategy_proceeds(tmp_path):
    insp = pd.inspect_profile(tmp_path / "fresh")
    assert pd.collision_strategy(insp) == pd.PROCEED


def test_strategy_reconfigures(tmp_path):
    root = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=True)
    insp = pd.inspect_profile(root)
    assert pd.collision_strategy(insp) == pd.RECONFIGURE


def test_strategy_demands_confirm(tmp_path):
    # A plain directory (no config.yaml) in the way.
    root = tmp_path / "random"
    root.mkdir()
    (root / "notes.txt").write_text("hi", encoding="utf-8")
    insp = pd.inspect_profile(root)
    assert insp.strategy == pd.CONFIRM_OVERWRITE
    assert insp.is_hermes_managed is False


def test_strategy_aborts_without_force(tmp_path):
    root = tmp_path / "random"
    root.mkdir()
    insp = pd.inspect_profile(root)  # confirm-overwrite
    assert pd.collision_strategy(insp, force=False) == pd.ABORT
    assert pd.collision_strategy(insp, force=True) == pd.OVERWRITE


def test_reconfigure_aborts_without_warroom_package(tmp_path):
    # Hermes profile with user data but NO warroom_setup package (corrupt/foreign):
    # cannot reconfigure -> abort (F18).
    root = tmp_path / "corrupt"
    root.mkdir()
    (root / "config.yaml").write_text("name: corrupt\n", encoding="utf-8")
    local = root / "local"
    local.mkdir()
    (local / "agent.json").write_text("{}", encoding="utf-8")
    insp = pd.inspect_profile(root)
    assert insp.has_user_data is True
    assert insp.has_warroom_setup is False
    assert insp.strategy == pd.ABORT
    assert pd.collision_strategy(insp) == pd.ABORT
    # Even a hand-built reconfigure recommendation is guarded:
    forced = pd.ProfileInspection(
        path=root, exists=True, is_hermes_managed=True, has_warroom_setup=False,
        has_user_data=True, strategy=pd.RECONFIGURE,
    )
    assert pd.collision_strategy(forced) == pd.ABORT

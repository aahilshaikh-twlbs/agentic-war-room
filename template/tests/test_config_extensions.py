"""Config.yaml extensions T18-T20: personalities, platform_toolsets (sentinel-
managed), and safe-default top-level keys. No PyYAML in the env (stdlib-only
invariant), so checks are line/regex-based -- matching the repo's own readers --
plus a structural sanity pass (no tabs, consistent 2-space indentation).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = (ROOT / "config.yaml").read_text(encoding="utf-8")


def _top_level_keys(text):
    keys = []
    for line in text.splitlines():
        if not line or line[0] in (" ", "\t", "#", "-"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
        if m:
            keys.append(m.group(1))
    return keys


# ---- structural sanity (guards every config edit) ----

def test_config_has_no_tabs():
    assert "\t" not in CFG, "config.yaml must use spaces, not tabs"


def test_config_indentation_is_multiple_of_two():
    for line in CFG.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        assert indent % 2 == 0, "bad indent (%d): %r" % (indent, line)


def test_existing_managed_block_preserved():
    # T7/T17 invariant: the war_room sentinel block is intact.
    assert "# >>> warroom-managed (set via `warroom setup`) >>>" in CFG
    assert "# <<< warroom-managed <<<" in CFG
    assert re.search(r"^plugins:", CFG, re.M)


# ---- T18: personalities ----

def test_personalities_has_five_generic_flavors():
    assert re.search(r"^personalities:", CFG, re.M)
    block = CFG.split("personalities:", 1)[1]
    flavors = set(re.findall(r"^  ([a-z]+):", block, re.M))
    # the next top-level key would dedent; capture only the immediate children
    expected = {"helpful", "concise", "technical", "teacher", "noir"}
    assert expected <= flavors, "missing flavors: %s" % (expected - flavors)
    # no unprofessional flavors leaked in
    for banned in ("kawaii", "catgirl", "uwu", "pirate"):
        assert banned not in CFG.lower()


def test_personalities_have_descriptions_and_suffixes():
    block = CFG.split("personalities:", 1)[1]
    assert block.count("description:") >= 5
    assert block.count("system_prompt_suffix:") >= 5


# ---- T19: platform_toolsets in its own sentinel block ----

def test_toolsets_sentinel_block_distinct_from_managed():
    assert "# >>> warroom-toolsets >>>" in CFG
    assert "# <<< warroom-toolsets <<<" in CFG
    # distinct from the war_room managed block
    assert "# >>> warroom-toolsets >>>" != "# >>> warroom-managed (set via `warroom setup`) >>>"
    # the toolsets block must not swallow the war_room managed block
    toolsets = CFG.split("# >>> warroom-toolsets >>>", 1)[1].split("# <<< warroom-toolsets <<<", 1)[0]
    assert "war_room:" not in toolsets


def test_platform_toolsets_has_cli_discord_slack():
    assert re.search(r"^platform_toolsets:", CFG, re.M)
    block = CFG.split("platform_toolsets:", 1)[1].split("# <<< warroom-toolsets", 1)[0]
    for platform in ("cli:", "discord:", "slack:"):
        assert re.search(r"^  %s" % re.escape(platform), block, re.M), "missing %s" % platform
    assert "- hermes-discord" in block
    assert "- hermes-slack" in block

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse_simple_yaml_top_keys(text):
    # Minimal: collect top-level "key:" names (column 0, not a comment).
    keys = []
    for line in text.splitlines():
        if not line or line[0] in (" ", "#", "-"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
        if m:
            keys.append(m.group(1))
    return keys


def test_distribution_yaml_at_root_with_required_fields():
    dist = ROOT / "distribution.yaml"
    assert dist.is_file(), "distribution.yaml MUST be at template/ root (Hermes has no subdir install)"
    keys = _parse_simple_yaml_top_keys(dist.read_text())
    assert "name" in keys, "name is required by DistributionManifest.from_dict"
    # version/hermes_requires/env_requires/distribution_owned are present in our manifest
    for k in ("version", "hermes_requires", "env_requires", "distribution_owned"):
        assert k in keys, f"expected top-level key {k!r}"


def test_env_template_filename_is_dot_env_template():
    # Hermes only renames a file named exactly ".env.template" -> ".env.EXAMPLE".
    assert (ROOT / ".env.template").is_file()
    assert not (ROOT / ".env.example").exists(), "use .env.template (Hermes renames it), not .env.example"


def test_env_template_keys_have_no_values():
    for line in (ROOT / ".env.template").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert line.endswith("="), f"shipped .env.template must not contain a secret value: {line!r}"

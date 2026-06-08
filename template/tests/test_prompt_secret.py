"""prompt_secret(label, current=None): masked secret entry (Task T4).

getpass.getpass is monkeypatched so the suite runs without a TTY.
"""
from warroom_setup import prompts


def test_returns_entered_value(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-secret")
    assert prompts.prompt_secret("Anthropic key") == "sk-secret"


def test_blank_keeps_current(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "")
    assert prompts.prompt_secret("Token", current="old-token") == "old-token"


def test_blank_with_no_current_returns_empty(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "")
    assert prompts.prompt_secret("Token") == ""


def test_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "  sk-xyz  ")
    assert prompts.prompt_secret("Token") == "sk-xyz"


def test_new_value_overrides_current(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "new-token")
    assert prompts.prompt_secret("Token", current="old-token") == "new-token"


def test_label_passed_to_getpass(monkeypatch):
    seen = {}

    def fake(prompt=""):
        seen["prompt"] = prompt
        return "x"

    monkeypatch.setattr("getpass.getpass", fake)
    prompts.prompt_secret("Slack token")
    assert "Slack token" in seen["prompt"]

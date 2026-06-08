"""CLI surface for lane claims (claim-lane / release-lane / list-lanes).

The engine already speaks lanes; these tests pin the *shell* surface that
exposes them. The critical invariant: a ``lane://`` URI passed on the command
line must be preserved verbatim and NEVER routed through ``os.path.abspath`` --
otherwise ``lane://x`` is mangled into ``<cwd>/lane:/x`` and silently fails to
match the engine's lane conflict scan.
"""

import os

from mailbox import cli, client


def test_lane_subcommands_parse():
    parser = cli.build_parser()
    for argv in (
        ["claim-lane", "fix-auth"],
        ["claim-lane", "fix-auth", "--note", "mine"],
        ["release-lane", "fix-auth"],
        ["list-lanes"],
    ):
        ns = parser.parse_args(argv)
        assert ns.cmd == argv[0]


def test_lane_name_helper_skips_abspath():
    # Bare name passes through unchanged.
    assert cli._lane_name("fix-auth") == "fix-auth"
    # lane:// URI has its prefix stripped for the engine (which re-adds it),
    # and is NEVER turned into an absolute filesystem path.
    out = cli._lane_name("lane://fix-auth")
    assert out == "fix-auth"
    assert os.getcwd() not in out
    assert "lane:/" not in out


def test_claim_lane_then_list_shows_it(tmp_home, capsys):
    client.ensure_running()
    sid = "sess-lane-1"

    assert cli.main(["--session", sid, "join", "--label", "alice"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "claim-lane", "fix-auth",
                     "--note", "auth work"]) == 0
    out = capsys.readouterr().out
    assert "allow" in out

    assert cli.main(["--session", sid, "list-lanes"]) == 0
    out = capsys.readouterr().out
    assert "fix-auth" in out
    assert "auth work" in out


def test_lane_uri_preserved_verbatim_not_abspathed(tmp_home, capsys):
    client.ensure_running()
    sid = "sess-lane-2"

    assert cli.main(["--session", sid, "join", "--label", "alice"]) == 0
    capsys.readouterr()

    # Pass the full lane:// URI form on the command line.
    assert cli.main(["--session", sid, "claim-lane", "lane://build-api"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "list-lanes"]) == 0
    out = capsys.readouterr().out
    # The lane is identified as build-api, not a cwd-mangled path.
    assert "build-api" in out
    assert os.getcwd() not in out
    assert "lane:/build-api" not in out  # the abspath footgun shape


def test_claim_lane_is_idempotent(tmp_home, capsys):
    client.ensure_running()
    sid = "sess-lane-3"

    assert cli.main(["--session", sid, "join", "--label", "alice"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "claim-lane", "fix-auth"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", sid, "claim-lane", "fix-auth"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "list-lanes"]) == 0
    out = capsys.readouterr().out
    # Exactly one lane line for fix-auth (idempotent re-claim).
    assert out.count("fix-auth") == 1


def test_release_lane_roundtrip(tmp_home, capsys):
    client.ensure_running()
    sid = "sess-lane-4"

    assert cli.main(["--session", sid, "join", "--label", "alice"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "claim-lane", "fix-auth"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "release-lane", "fix-auth"]) == 0
    capsys.readouterr()

    assert cli.main(["--session", sid, "list-lanes"]) == 0
    out = capsys.readouterr().out
    assert "(no lanes)" in out

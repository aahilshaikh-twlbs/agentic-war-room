from warroom_setup import cli


def test_parser_setup_flags():
    parser = cli._build_parser()
    args = parser.parse_args(["setup", "--yes"])
    assert args.cmd == "setup" and args.yes is True and args.reconfigure is False
    args = parser.parse_args(["setup", "--reconfigure"])
    assert args.reconfigure is True
    args = parser.parse_args(["setup", "--sync"])
    assert args.sync is True


def test_no_command_prints_help_and_returns_2(capsys):
    rc = cli.main([])
    assert rc == 2


def test_keyboard_interrupt_returns_130(monkeypatch):
    def boom(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli.setup, "run_setup", boom)
    rc = cli.main(["setup", "--yes"])
    assert rc == 130

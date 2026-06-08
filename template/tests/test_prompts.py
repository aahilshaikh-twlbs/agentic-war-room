import io
from warroom_setup import prompts
from warroom_setup.selectables import TextField


def test_collect_required_reprompts_until_nonempty():
    fields = [TextField(id="agent_name", prompt="name", required=True)]
    instream = io.StringIO("\n\nzed\n")     # two blanks rejected, then "zed"
    outstream = io.StringIO()
    values = prompts.collect(fields, selected_toggles=set(),
                             in_stream=instream, out_stream=outstream)
    assert values["agent_name"] == "zed"


def test_enable_if_skips_field_when_toggle_off():
    fields = [TextField(id="SLACK_BOT_TOKEN", prompt="slack", enable_if="channels.slack")]
    instream = io.StringIO("")
    outstream = io.StringIO()
    values = prompts.collect(fields, selected_toggles=set(),  # slack NOT selected
                             in_stream=instream, out_stream=outstream)
    assert "SLACK_BOT_TOKEN" not in values


def test_enable_if_asks_field_when_toggle_on():
    fields = [TextField(id="SLACK_BOT_TOKEN", prompt="slack", enable_if="channels.slack")]
    instream = io.StringIO("xoxb-123\n")
    outstream = io.StringIO()
    values = prompts.collect(fields, selected_toggles={"channels.slack"},
                             in_stream=instream, out_stream=outstream)
    assert values["SLACK_BOT_TOKEN"] == "xoxb-123"


def test_optional_blank_is_recorded_as_empty():
    fields = [TextField(id="handle", prompt="handle", required=False)]
    instream = io.StringIO("\n")
    outstream = io.StringIO()
    values = prompts.collect(fields, selected_toggles=set(),
                             in_stream=instream, out_stream=outstream)
    assert values.get("handle", "") == ""

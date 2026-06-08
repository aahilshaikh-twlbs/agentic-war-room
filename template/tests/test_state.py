from warroom_setup import selectables
from warroom_setup.state import WizardState


def _stages():
    return selectables.build_stages(selectables.TOGGLES)


def test_move_clamps_within_stage():
    st = WizardState(_stages(), set())
    assert st.cursor == 0
    st.move(-1)
    assert st.cursor == 0           # clamps at top of single-entry first stage
    st.next_stage()                  # Persona -> Channels (2 entries: discord, slack)
    st.move(1)
    assert st.cursor == 1            # advances within multi-entry stage
    st.move(1)
    assert st.cursor == 1            # clamps at bottom (Channels has only 2 entries)


def test_toggle_adds_and_removes():
    st = WizardState(_stages(), set())
    first = st.current_stage().entries[0].id
    st.toggle()
    assert st.is_selected(first)
    st.toggle()
    assert not st.is_selected(first)


def test_next_stage_then_review_then_confirm():
    st = WizardState(_stages(), set())
    for _ in range(len(_stages())):
        st.next_stage()
    assert st.is_review()
    assert not st.is_done()
    st.confirm()
    assert st.is_done()


def test_prev_from_review_returns_to_last_stage():
    st = WizardState(_stages(), set())
    for _ in range(len(_stages())):
        st.next_stage()
    assert st.is_review()
    st.prev_stage()
    assert not st.is_review()

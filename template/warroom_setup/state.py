"""Pure, I/O-free wizard state machine. Stdlib only, Python >=3.9.

Direct port of ccpkg/wizard.py::WizardState (the settings.json-specific soft
warning is dropped; it has no analog here). Renderers in render.py drive this.
"""
from typing import List, Set

from .selectables import Stage


class WizardState:
    def __init__(self, stages, preselected):
        # type: (List[Stage], Set[str]) -> None
        self.stages = stages
        self.selected = set(preselected)
        self.stage_index = 0
        self.cursor = 0
        self._done = False
        self._review = False

    def current_stage(self):
        return self.stages[self.stage_index]

    def is_selected(self, entry_id):
        return entry_id in self.selected

    def is_review(self):
        return self._review

    def is_done(self):
        return self._done

    def selected_ids(self):
        return set(self.selected)

    def move(self, delta):
        n = len(self.current_stage().entries)
        if n == 0:
            self.cursor = 0
            return
        self.cursor = max(0, min(n - 1, self.cursor + delta))

    def toggle(self):
        entries = self.current_stage().entries
        if not entries:
            return
        eid = entries[self.cursor].id
        if eid in self.selected:
            self.selected.discard(eid)
        else:
            self.selected.add(eid)

    def select_all(self):
        for e in self.current_stage().entries:
            self.selected.add(e.id)

    def select_none(self):
        for e in self.current_stage().entries:
            self.selected.discard(e.id)

    def next_stage(self):
        if self.stage_index >= len(self.stages) - 1:
            self._review = True
            return
        self.stage_index += 1
        self.cursor = 0

    def confirm(self):
        self._done = True

    def prev_stage(self):
        if self._review:
            self._review = False
            return
        if self._done:
            self._done = False
            return
        if self.stage_index > 0:
            self.stage_index -= 1
            self.cursor = 0

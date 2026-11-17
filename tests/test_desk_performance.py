import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from desk_ui import PersonalDesk


class DeskRefreshTests(unittest.TestCase):
    def test_unchanged_snapshot_does_not_rebuild_but_changed_snapshot_does(self):
        desk = Mock()
        desk.owner.session_user = {'id': 'u', 'fullname': 'کاربر'}
        desk.owner.data = {}
        desk.snapshot = {}
        desk.queued = set()
        value = {'user_id': 'u', 'notes': [], 'notifications': []}
        PersonalDesk.apply_snapshot(desk, value)
        self.assertEqual(desk.owner.refresh.call_count, 1)
        PersonalDesk.apply_snapshot(desk, copy.deepcopy(value))
        self.assertEqual(desk.owner.refresh.call_count, 1)
        self.assertEqual(desk.render_notes.call_count, 1)
        changed = dict(value, notes=[{'id': 'new'}])
        PersonalDesk.apply_snapshot(desk, changed)
        self.assertEqual(desk.owner.refresh.call_count, 2)
        self.assertEqual(desk.render_notes.call_count, 2)


if __name__ == '__main__':
    unittest.main()

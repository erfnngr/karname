import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

import jdatetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

import storage
from birthday_service import (
    build_reminder_copy,
    is_user_birthday_today,
    next_birthday_occurrence,
    parse_birthday,
    resolve_birthday_for_year,
)
from org_http import RunningServer
from org_client import Client
from org_store import Store
from weather import parse_forecast, parse_openmeteo, weather_kind, TEHRAN
import test_v6_ui as fixtures


class BirthdayServiceTests(unittest.TestCase):
    def test_nonexistent_leap_day_policies(self):
        # 1370 was a Jalali leap year with Esfand 30; 1405 is non-leap (29 days in Esfand)
        leap_bday = parse_birthday({'year': 1370, 'month': 12, 'day': 30, 'missing_day_policy': 'last_day_of_month'})
        self.assertEqual(leap_bday['date_jalali'], '1370/12/30')

        last_day = resolve_birthday_for_year(leap_bday, 1405, default_policy='last_day_of_month')
        self.assertEqual((last_day.year, last_day.month, last_day.day), (1405, 12, 29))

        leap_next = dict(leap_bday, missing_day_policy='next_day')
        next_day = resolve_birthday_for_year(leap_next, 1405)
        self.assertEqual((next_day.year, next_day.month, next_day.day), (1406, 1, 1))

        leap_skip = dict(leap_bday, missing_day_policy='skip')
        self.assertIsNone(resolve_birthday_for_year(leap_skip, 1405))

    def test_three_day_reminder_excludes_birthday_person_dedups_and_cancels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'company-server')
            alice = store.bootstrap('alice', 'Pass-123456', 'آلیس کریمی', 'آلیس', 'کریمی')
            bob = store.user(
                store.save_user(
                    alice,
                    dict(
                        username='bob',
                        password='Pass-123456',
                        first_name='بابک',
                        last_name='رضایی',
                        memberships=[dict(company_id='mana', role='employee')],
                    ),
                )['id']
            )
            charlie = store.user(
                store.save_user(
                    alice,
                    dict(
                        username='charlie',
                        password='Pass-123456',
                        first_name='سارا',
                        last_name='احمدی',
                        memberships=[dict(company_id='mana', role='employee')],
                    ),
                )['id']
            )

            today_g = date.today()
            target_g = today_g + timedelta(days=3)
            target_jd = jdatetime.date.fromgregorian(date=target_g)
            # Pick valid birth year 1370 if Esfand 30 else 1375
            birth_year = 1370 if (target_jd.month == 12 and target_jd.day == 30) else 1375
            bday = parse_birthday({'year': birth_year, 'month': target_jd.month, 'day': target_jd.day})

            store.save_profile(alice, {'preferences': {'birthday': bday}})

            # Alice must NOT receive a reminder for her own birthday
            alice_snap = store.birthdays_snapshot(alice, today_g=today_g)
            self.assertEqual(alice_snap['reminders'], [])
            self.assertEqual(alice_snap['own_birthday']['date_jalali'], bday['date_jalali'])

            # Bob and Charlie each get exactly ONE reminder naming Alice and her birthday
            bob_snap = store.birthdays_snapshot(bob, today_g=today_g)
            charlie_snap = store.birthdays_snapshot(charlie, today_g=today_g)
            self.assertEqual(len(bob_snap['reminders']), 1)
            self.assertEqual(len(charlie_snap['reminders']), 1)
            self.assertIn('آلیس کریمی', bob_snap['reminders'][0]['body'])
            self.assertEqual(bob_snap['reminders'][0]['birthday_year'], target_jd.year)

            # Re-running reconciliation produces zero duplicates for the same year
            store.reconcile_birthday_reminders(today_g=today_g)
            self.assertEqual(len(store.birthdays_snapshot(bob, today_g=today_g)['reminders']), 1)

            # Edit Alice's birthday to 2 days later (outside 3-day window) -> reminder cancelled!
            later_jd = jdatetime.date.fromgregorian(date=today_g + timedelta(days=40))
            later_year = 1370 if (later_jd.month == 12 and later_jd.day == 30) else 1375
            store.save_profile(alice, {'preferences': {'birthday': parse_birthday({'year': later_year, 'month': later_jd.month, 'day': later_jd.day})}})
            self.assertEqual(store.birthdays_snapshot(bob, today_g=today_g)['reminders'], [])

            # Move Alice's birthday to 2 days from today (e.g. network reconnect catch-up) -> reminder recreated/updated!
            soon_jd = jdatetime.date.fromgregorian(date=today_g + timedelta(days=2))
            soon_year = 1370 if (soon_jd.month == 12 and soon_jd.day == 30) else 1375
            store.save_profile(alice, {'preferences': {'birthday': parse_birthday({'year': soon_year, 'month': soon_jd.month, 'day': soon_jd.day})}})
            self.assertEqual(len(store.birthdays_snapshot(bob, today_g=today_g)['reminders']), 1)

            # Remove Alice's birthday -> reminder cancelled again!
            store.save_profile(alice, {'preferences': {'birthday': None}})
            self.assertEqual(store.birthdays_snapshot(bob, today_g=today_g)['reminders'], [])


class BirthdayUiAndEnhancementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        fixtures.V6UiTests.setUp(self)

    def tearDown(self):
        fixtures.V6UiTests.tearDown(self)

    pump = fixtures.V6UiTests.pump

    def test_birthday_settings_offline_reconnect_and_once_per_year_celebration(self):
        from settings_ui import SettingsDialog

        today_jd = storage.today_j()
        birth_year = 1370 if (today_jd.month == 12 and today_jd.day == 30) else 1374

        # 1) Create & edit birthday in Settings UI while temporarily offline, then reconnect -> syncs to server!
        saved_client = self.win.org.client
        self.win.org.client = None
        dlg = SettingsDialog(self.win)
        dlg.personal.birthday_enabled.setChecked(True)
        dlg.personal.birthday_year.setCurrentIndex(dlg.personal.birthday_year.findData(birth_year))
        dlg.personal.birthday_month.setCurrentIndex(dlg.personal.birthday_month.findData(today_jd.month))
        dlg.personal.birthday_day.setCurrentIndex(dlg.personal.birthday_day.findData(today_jd.day))
        dlg.validate()
        self.assertEqual(dlg.result(), QDialog.Accepted)
        self.assertTrue(self.win.data.get('pending_birthday_sync'))
        dlg.deleteLater()

        # Reconnect and trigger org.sync() -> pending birthday pushes to server!
        self.win.org.client = saved_client
        self.win.org.sync()
        fixtures.V6UiTests.pump(self, lambda: not self.win.org.busy and not self.win.data.get('pending_birthday_sync'))
        prof = self.store.own_profile(self.admin)
        self.assertEqual(prof['preferences']['birthday']['day'], today_jd.day)

        # 2) Celebration launches automatically on user's birthday (once per year), shows «تولدت مبارک، ...!», transitions to cake & blows candle
        self.pump(lambda: getattr(self.win, '_birthday_overlay', None) is not None)
        overlay = self.win._birthday_overlay
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.phase, 'greeting')
        self.assertTrue(overlay.isVisible())

        # Second call same day/year MUST NOT show celebration again!
        self.assertIsNone(self.win.check_birthday_celebration())

        # Fast-forward greeting 5s timer -> cake & clickable lit candle phase
        overlay.banner_duration_ms = 200
        overlay._elapsed_ms = 210
        overlay._step()
        self.assertEqual(overlay.phase, 'cake')
        self.assertTrue(overlay.cake_visible)
        self.assertTrue(overlay.flame_lit)
        self.assertTrue(overlay.candle_button.isVisible())

        # Click candle -> extinguishes flame and closes smoothly
        overlay.candle_button.click()
        self.assertFalse(overlay.flame_lit)
        self.assertEqual(overlay.phase, 'blowing')
        self.pump(lambda: getattr(self.win, '_birthday_overlay', None) is None)

        # Simulating reopening app on the same birthday same year: MUST still NOT show!
        self.assertIsNone(self.win.check_birthday_celebration())

        # Teammate account whose birthday is NOT today never sees celebration
        staff_id = self.store.users(self.admin)[-1]['id']
        self.win.session_user = {'id': staff_id, 'fullname': 'کارمند نمونه'}
        self.win.data['preferences'].pop('birthday', None)
        self.assertIsNone(self.win.check_birthday_celebration())

    def test_weather_nighttime_hours_show_moon_not_sun(self):
        # 22:00 Tehran (18:30 UTC) clear sky must classify as 'moon', not 'sun'
        now = datetime(2026, 11, 15, 18, 30, tzinfo=timezone.utc)
        local = now.astimezone(TEHRAN)
        hours_t = [(local + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M') for i in range(24)]
        days_t = [(local + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        model = {
            'utc_offset_seconds': 12600,
            'current': {'time': local.strftime('%Y-%m-%dT%H:%M'), 'temperature_2m': 11, 'weather_code': 0, 'is_day': 0},
            'hourly': {
                'time': hours_t,
                'temperature_2m': [10 + i * 0.2 for i in range(24)],
                'weather_code': [0] * 24,
                'is_day': [0 if i < 9 else 1 for i in range(24)],
            },
            'daily': {'time': days_t, 'temperature_2m_min': [6] * 7, 'temperature_2m_max': [16] * 7, 'weather_code': [0] * 7},
        }
        res = parse_openmeteo(model, now)
        self.assertEqual(weather_kind(res['current']['symbol'])[0], 'moon')
        self.assertEqual(weather_kind(res['hours'][0]['symbol'])[0], 'moon')
        self.assertEqual(weather_kind(res['hours'][10]['symbol'])[0], 'sun')

        # Even if upstream payload omits is_day completely, local night timestamp (23:00) resolves to moon
        self.assertEqual(weather_kind({'code': 0, 'fa': 'صاف'}, at_time=local.replace(hour=23))[0], 'moon')
        self.assertEqual(weather_kind({'code': 1, 'fa': 'عمدتاً صاف'}, at_time=local.replace(hour=23))[0], 'cloud-moon')

    def test_frameless_menus_shortcuts_qss_sync_and_fullscreen_grid(self):
        from navigation_shortcuts import activate, help_text, toggle_theme
        from theme_catalog import THEMES

        # 1) Top nav menus must have frameless / translucent flags (no black DWM box)
        for m in (self.win.calendar_menu, self.win.services_menu, self.win.desk_menu):
            self.assertTrue(bool(m.windowFlags() & Qt.FramelessWindowHint))
            self.assertTrue(bool(m.windowFlags() & Qt.NoDropShadowWindowHint))
            self.assertTrue(m.testAttribute(Qt.WA_TranslucentBackground))

        # 2) First-letter shortcuts & help text
        self.assertIn('Ctrl+Shift+T', help_text())
        self.assertIn('Ctrl+Shift+H', help_text())
        self.assertTrue(activate(self.win, 'tax'))
        self.assertIs(self.win.tabs.currentWidget(), self.win.tax_center)
        self.assertTrue(activate(self.win, 'home'))
        self.assertIs(self.win.tabs.currentWidget(), self.win.home)

        # 3) Liquid navbar/sidebar active across all 5 themes and toggling dark updates QSS cleanly
        for preset_key, _, _ in THEMES:
            self.win.data['settings']['theme_preset'] = preset_key
            self.win.sidebar.apply()
            toggle_theme(self.win)
            self.app.processEvents()
            # Ensure SettingsDialog picks up clean dark/light styles immediately without stale deferred QSS
            from settings_ui import SettingsDialog
            d = SettingsDialog(self.win)
            self.assertTrue(d.styleSheet())
            d.deleteLater()
            toggle_theme(self.win)
            self.app.processEvents()

        # 4) Calendar grid stretches uniformly in maximized/fullscreen window sizes
        self.win.resize(1920, 1080)
        self.win.render_calendar()
        self.app.processEvents()
        for col in range(7):
            self.assertEqual(self.win.grid.columnStretch(col), 1)
        for row in range(1, 7):
            self.assertEqual(self.win.grid.rowStretch(row), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

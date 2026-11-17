import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['KARNAME_FORCE_REACT_VIEWS'] = '1'
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --no-sandbox')

from react_design_host import register_design_scheme

register_design_scheme()

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import storage
import test_lmstudio as endpoints
from app import TaxWindow
from navigation_shortcuts import toggle_theme
from org_client import Client
from org_http import RunningServer
from org_store import Store
from tax_workflows import WORKFLOWS, workflow_progress


class ReactWebEngineE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env_patch = patch.dict(os.environ, {'TAXCALENDAR_DATA_DIR': str(self.root)})
        self.env_patch.start()
        storage.set_profile(None)
        data = storage.load_data()
        data['settings'].update(news_enabled=False, reminder_enabled=False, theme='light', theme_preset='glass_mist')
        storage.save_data(data)

        self.store = Store(self.root / 'company-server')
        self.admin = self.store.bootstrap('admin', '1', 'مدیر آزمون')
        self.store.save_user(
            self.admin,
            dict(
                username='staff',
                password='ک',
                fullname='همکار آزمون',
                memberships=[dict(company_id='mana', role='employee')],
            ),
        )
        self.server = RunningServer(self.root / 'company-server', '127.0.0.1', 0)
        self.client = Client('http://127.0.0.1:' + str(self.server.port))
        self.user = self.client.login('admin', '1')
        self.win = TaxWindow(dict(user=self.user, client=self.client, local_server=self.server), self.root)
        self.win.v8.timer.stop()
        self.win.v8.stop.set()
        self.win.workspace.timer.stop()
        self.win.resize(1280, 820)
        self.win.show()
        self.pump(lambda: not self.win.org.busy, timeout=10.0)
        self.win.timer.stop()
        self.win.news_panel.timer.stop()
        self.win.org.timer.stop()
        self.win.desk.timer.stop()
        self.win.chat.timer.stop()

    def tearDown(self):
        self.win.ai.cancel()
        self.win._exit_approved = True
        self.win.v8.timer.stop()
        self.win.v8.stop.set()
        self.win.workspace.timer.stop()
        self.win.chat.timer.stop()
        self.win.org.timer.stop()
        self.win.desk.timer.stop()
        self.win.news_panel.timer.stop()
        self.win.home.weather_service.timer.stop()
        self.win.timer.stop()
        for panel in (self.win.home, self.win.calendar_page, self.win.chat, self.win.ai, self.win.tax_center):
            rv = getattr(panel, 'react_view', None)
            if rv is not None:
                rv.bridge.close()
                if hasattr(rv, 'appearance'):
                    rv.appearance.timer.stop()
                rv.view.setPage(None)
                rv.page.deleteLater()
        if self.win.tray:
            self.win.tray.hide()
        self.win.company_server = None
        self.win.close()
        self.win.deleteLater()
        self.app.processEvents()
        self.server.close()
        storage.set_profile(None)
        self.env_patch.stop()
        self.temp.cleanup()

    def pump(self, condition=None, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            self.app.processEvents()
            time.sleep(0.015)
            if condition is None or condition():
                return
        raise AssertionError('Timed out waiting for UI condition')

    def eval_js(self, page, script, timeout=8.0):
        done = []
        page.runJavaScript(script, lambda val: done.append(val))
        self.pump(lambda: bool(done), timeout=timeout)
        return done[0]

    def wait_js(self, page, expr, timeout=15.0):
        end = time.time() + timeout
        last_val = None
        while time.time() < end:
            last_val = self.eval_js(page, f'(() => Boolean({expr}))()', timeout=5.0)
            if last_val:
                return
            time.sleep(0.05)
        raise AssertionError(f'Timed out waiting for JS condition: {expr} (last={last_val!r})')

    def test_chat_react_view_theme_draft_group_and_message_e2e(self):
        self.win.tabs.setCurrentWidget(self.win.chat)
        self.pump(lambda: getattr(self.win.chat, 'react_view', None) is not None, timeout=10.0)
        rv = self.win.chat.react_view
        self.assertIsNotNone(rv)
        page = rv.page

        self.wait_js(page, "document.body && document.body.innerText.includes('چت‌ها')")

        # Verify no fake sample data from chat-template.tsx is visible
        body_text = self.eval_js(page, 'document.body.innerText')
        for fake in ('Alice', 'Charlie', 'Design Systems'):
            self.assertNotIn(fake, body_text)

        # Verify Saved Messages room appears once (auto-provisioned for the user) and '+' menu opens cleanly
        self.wait_js(
            page,
            "Array.from(document.querySelectorAll('aside button')).filter(b => b.innerText.includes('پیام‌های ذخیره‌شده')).length === 1",
        )
        # Open '+' menu via real Qt click and create a real group through React UI
        self.wait_js(page, "document.querySelector('button[aria-label=\"شروع گفتگوی تازه\"]') !== null")
        rect_raw = self.eval_js(
            page,
            """(() => {
                const trigger = document.querySelector('button[aria-label="شروع گفتگوی تازه"]');
                if (!trigger) return '';
                const r = trigger.getBoundingClientRect();
                return Math.round(r.left + r.width / 2) + ',' + Math.round(r.top + r.height / 2);
            })()""",
        )
        self.assertTrue(rect_raw and ',' in str(rect_raw), f'Bad trigger rect: {rect_raw!r}')
        x_str, y_str = str(rect_raw).split(',')
        target_widget = rv.view.focusProxy() or rv.view
        QTest.mouseClick(target_widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(x_str), int(y_str)))
        self.wait_js(
            page,
            "document.body.innerText.includes('گفتگوی شخصی تازه') && document.body.innerText.includes('ساخت گروه جدید')",
        )
        self.eval_js(
            page,
            """(() => {
                const items = Array.from(document.querySelectorAll('[role="menuitem"]'));
                const grp = items.find(el => el.innerText.includes('ساخت گروه جدید'));
                grp && grp.click();
            })()""",
        )
        self.wait_js(page, "document.querySelector('input[placeholder=\"نام گروه\"]') !== null")
        self.eval_js(
            page,
            """(() => {
                const inp = document.querySelector('input[placeholder="نام گروه"]');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, 'گروه وب آزمون');
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                const cb = document.querySelector('section[role="dialog"] input[type="checkbox"]');
                if (cb && !cb.checked) cb.click();
                setTimeout(() => {
                    const submit = Array.from(document.querySelectorAll('section[role="dialog"] button')).find(b => b.innerText.trim() === 'ساخت گروه');
                    submit && submit.click();
                }, 40);
            })()""",
        )
        self.wait_js(page, "document.body.innerText.includes('گروه وب آزمون')")

        # Verify light & dark mode appearance sync inside WebEngine DOM
        self.assertFalse(self.eval_js(page, "document.documentElement.classList.contains('dark')"))
        toggle_theme(self.win)
        rv.appearance.publish()
        self.wait_js(page, "document.documentElement.classList.contains('dark')")
        toggle_theme(self.win)
        rv.appearance.publish()
        self.wait_js(page, "!document.documentElement.classList.contains('dark')")

        # Verify created group exists in real backend store
        rooms = self.store.chat_rooms(self.admin)
        created = next(r for r in rooms if r.get('title') == 'گروه وب آزمون')

        # Select Saved Messages room and type a draft
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('aside button')).find(b => b.innerText.includes('پیام‌های ذخیره‌شده'));
                btn && btn.click();
            })()""",
        )
        self.wait_js(page, "document.querySelector('textarea:not([disabled])') !== null")

        self.eval_js(
            page,
            """(() => {
                const ta = document.querySelector('textarea:not([disabled])');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(ta, 'پیش‌نویس ماندگار چت');
                ta.dispatchEvent(new Event('input', { bubbles: true }));
            })()""",
        )

        # Switch to group room -> confirm clean composer -> switch back -> confirm draft preserved
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('aside button')).find(b => b.innerText.includes('گروه وب آزمون'));
                btn && btn.click();
            })()""",
        )
        self.wait_js(page, "(document.querySelector('textarea:not([disabled])')?.value ?? null) === ''")
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('aside button')).find(b => b.innerText.includes('پیام‌های ذخیره‌شده'));
                btn && btn.click();
            })()""",
        )
        self.wait_js(
            page,
            "(document.querySelector('textarea:not([disabled])')?.value || '') === 'پیش‌نویس ماندگار چت'",
        )

        # Send real message from the group room and verify it arrives on real server & renders in DOM
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('aside button')).find(b => b.innerText.includes('گروه وب آزمون'));
                btn && btn.click();
            })()""",
        )
        self.wait_js(page, "(document.querySelector('textarea:not([disabled])')?.value ?? null) === ''")
        self.eval_js(
            page,
            """(() => {
                const ta = document.querySelector('textarea:not([disabled])');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(ta, 'سلام از رابط جدید');
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                setTimeout(() => {
                    const sendBtn = document.querySelector('button[aria-label="ارسال"]');
                    sendBtn && sendBtn.click();
                }, 40);
            })()""",
        )
        self.wait_js(
            page,
            "(document.querySelector('textarea:not([disabled])')?.value ?? null) === '' && document.body.innerText.includes('سلام از رابط جدید')",
        )
        self.pump(
            lambda: any(
                m.get('text') == 'سلام از رابط جدید'
                for m in self.store.chat_list(self.admin, '__shared_chat__', created['room'])['items']
            ),
            timeout=10.0,
        )

    def test_assistant_react_view_followup_and_real_result_e2e(self):
        lm_fixture = endpoints.LMClientTests()
        lm_fixture.setUp()
        try:
            with patch('ai_chat_ui.GEMMA_MODEL', 'local-chat'), patch('ai_chat_ui.token', return_value=''):
                self.win.data['settings']['lmstudio'] = {'url': lm_fixture.client.url, 'model': ''}
                endpoints.FakeLM.mode = 'app_followup'
                ai = self.win.ai
                ai.mode.setCurrentIndex(2)  # Application assistant mode
                before_events = len(self.win.events)

                self.win.tabs.setCurrentWidget(ai)
                self.pump(lambda: getattr(ai, 'react_view', None) is not None, timeout=10.0)
                rv = ai.react_view
                page = rv.page

                self.wait_js(
                    page,
                    "document.body && document.body.innerText.includes('دستیار برنامه') && document.querySelector('button[aria-label=\"Open prompt input\"]') !== null",
                )

                # Expand PromptInput and send ambiguous first message
                self.eval_js(
                    page,
                    """(() => {
                        const openBtn = document.querySelector('button[aria-label="Open prompt input"]');
                        openBtn && openBtn.click();
                        const ta = document.querySelector('textarea[aria-label="Prompt"]');
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                        setter.call(ta, 'برای پیگیری اظهارنامه یادآور بساز');
                        ta.dispatchEvent(new Event('input', { bubbles: true }));
                        setTimeout(() => {
                            ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                        }, 40);
                    })()""",
                )
                self.wait_js(page, "document.body.innerText.includes('چه تاریخی')")
                self.pump(lambda: not ai.busy and not ai.applying, timeout=10.0)

                # Send short follow-up -> detected as continuation -> executes real action & renders result card
                self.eval_js(
                    page,
                    """(() => {
                        const openBtn = document.querySelector('button[aria-label="Open prompt input"]');
                        openBtn && openBtn.click();
                        const ta = document.querySelector('textarea[aria-label="Prompt"]');
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                        setter.call(ta, '1405/09/01');
                        ta.dispatchEvent(new Event('input', { bubbles: true }));
                        setTimeout(() => {
                            ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                        }, 40);
                    })()""",
                )
                self.wait_js(page, "document.body.innerText.includes('نتیجه واقعی انجام کار در برنامه')", timeout=15.0)
                self.pump(lambda: len(self.win.events) > before_events, timeout=10.0)
                self.assertEqual(self.win.events[-1]['date_jalali'], '1405/09/01')
                self.assertEqual(self.win.events[-1]['title'], 'پیگیری اظهارنامه')
        finally:
            self.win.ai.cancel()
            lm_fixture.tearDown()

    def test_tax_react_view_roadmap_switch_complete_and_no_calendar_e2e(self):
        rec = self.client.request(
            'records',
            dict(
                kind='tax_case',
                company='mana',
                payload=dict(
                    title='اظهارنامه فصل بهار ۱۴۰۴',
                    tax_type='ارزش افزوده',
                    period='1404/01',
                    due_date='1404/04/15',
                    status='draft',
                ),
            ),
        )
        self.win.org.sync()
        self.pump(lambda: not self.win.org.busy, timeout=10.0)

        self.win.tabs.setCurrentWidget(self.win.tax_center)
        self.pump(lambda: getattr(self.win.tax_center, 'react_view', None) is not None, timeout=10.0)
        rv = self.win.tax_center.react_view
        page = rv.page

        self.wait_js(page, "document.querySelectorAll('[data-tax-step-index]').length > 0")
        rv.bridge.publish()

        # Confirm NO calendar button exists inside Tax view
        cal_btns = self.eval_js(
            page,
            "Array.from(document.querySelectorAll('button, a')).filter(el => el.innerText.includes('تقویم')).length",
        )
        self.assertEqual(cal_btns, 0)

        # Switch category -> roadmap updates dynamically
        self.eval_js(
            page,
            """(() => {
                const btn = document.querySelector('[data-tax-category="بیمه کارکنان"]');
                btn && btn.click();
            })()""",
        )
        self.wait_js(
            page,
            f"document.querySelectorAll('[data-tax-step-index]').length === {len(WORKFLOWS['بیمه کارکنان'])}",
        )

        # Switch back to ارزش افزوده & verify steps + select created record
        self.eval_js(
            page,
            """(() => {
                const btn = document.querySelector('[data-tax-category="ارزش افزوده"]');
                btn && btn.click();
            })()""",
        )
        self.wait_js(
            page,
            f"document.querySelectorAll('[data-tax-step-index]').length === {len(WORKFLOWS['ارزش افزوده'])}",
        )
        self.eval_js(
            page,
            f"""(() => {{
                const sel = document.querySelector('select[aria-label="پرونده مالیاتی"]');
                if (sel) {{
                    sel.value = {rec['id']!r};
                    sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }})()""",
        )
        self.wait_js(page, "document.body.innerText.includes('اظهارنامه فصل بهار ۱۴۰۴')")

        # Click step 0 card -> opens step detail modal -> click «تکمیل» -> light green + checkmark + saved
        self.eval_js(
            page,
            """(() => {
                const card = document.querySelector('[data-tax-step-index="0"]');
                card && card.click();
            })()""",
        )
        self.wait_js(page, "document.querySelector('[data-tax-complete-button=\"true\"]') !== null")
        self.eval_js(
            page,
            """(() => {
                const btn = document.querySelector('[data-tax-complete-button="true"]');
                btn && btn.click();
            })()""",
        )
        self.wait_js(
            page,
            "document.querySelector('[data-tax-step-index=\"0\"]')?.getAttribute('data-tax-step-done') === 'true'",
        )
        saved = self.client.request('record', id=rec['id'])
        self.assertTrue(workflow_progress(saved['payload'])[0])

    def test_react_home_weather_and_actions_e2e(self):
        from datetime import date, datetime, timedelta

        self.win.tabs.setCurrentWidget(self.win.home)
        self.pump(lambda: getattr(self.win.home, 'react_view', None) is not None, timeout=10.0)
        rv = self.win.home.react_view
        page = rv.page

        self.wait_js(page, "document.body && document.body.innerText.includes('امروز من') && document.querySelector('[data-ai-briefing=\"true\"]') !== null && document.querySelector('.sea-welcome-hero') !== null && !document.body.innerText.includes('جستجو و فرمان') && document.querySelector('.sea-home-shell') !== null && document.querySelector('.sea-karname-watermark img') !== null")
        self.assertIn('home.html', page.url().toString())
        # Verify Daily Quote footer rendered when daily_quote_enabled is True
        self.wait_js(page, "document.querySelector('footer') !== null && document.querySelector('footer').innerText.trim().length > 0")

        # Populate live WeatherService snapshot and ensure preserved Weather UI + Details modal work
        now = datetime.now()
        today = date.today()
        ws = self.win.home.weather_service
        ws.data = {
            'current': {
                'time': now,
                'temp': 24.6,
                'humidity': 31,
                'wind': 4.2,
                'symbol': 'clearsky_day',
                'observation': {'station_name': 'مهرآباد'},
            },
            'hours': [
                {'time': now + timedelta(hours=1), 'temp': 26.0, 'symbol': 'clearsky_day'},
                {'time': now + timedelta(hours=2), 'temp': 23.0, 'symbol': 'partlycloudy_day'},
            ],
            'days': [
                {'date': today, 'min': 16.0, 'max': 27.0, 'symbol': 'clearsky_day'},
                {'date': today + timedelta(days=1), 'min': 15.0, 'max': 25.0, 'symbol': 'partlycloudy_day'},
            ],
        }
        ws.checked_at = now
        ws.error = ''
        ws.cached = False
        ws.changed.emit()
        rv.bridge.publish()

        self.wait_js(page, "document.body.innerText.includes('آب‌وهوای تهران') && document.body.innerText.includes('رطوبت ۳۱٪')")
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'جزئیات');
                btn && btn.click();
            })()""",
        )
        self.wait_js(page, "document.body.innerText.includes('جزئیات آب‌وهوای تهران') && document.body.innerText.includes('مهرآباد')")
        self.eval_js(
            page,
            """(() => {
                const closeBtn = Array.from(document.querySelectorAll('div[role="dialog"] button, button')).find(b => b.innerText.trim() === 'بستن');
                closeBtn && closeBtn.click();
            })()""",
        )
        self.wait_js(page, "!document.body.innerText.includes('جزئیات آب‌وهوای تهران')")

        # Verify light/dark mode sync
        self.assertFalse(self.eval_js(page, "document.documentElement.classList.contains('dark')"))
        toggle_theme(self.win)
        rv.appearance.publish()
        self.wait_js(page, "document.documentElement.classList.contains('dark')")
        toggle_theme(self.win)
        rv.appearance.publish()
        self.wait_js(page, "!document.documentElement.classList.contains('dark')")

        # Click 'امروز من' -> switches tab to Workspace / My Day
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('امروز من'));
                btn && btn.click();
            })()""",
        )
        self.pump(lambda: self.win.tabs.currentWidget() is self.win.workspace and self.win.workspace.view.currentIndex() == 2, timeout=8.0)

        # Switch back to Home and verify per-section custom theme tokens update DOM live without affecting locked Tax
        self.win.tabs.setCurrentWidget(self.win.home)
        self.win.data['settings']['custom_themes'] = {
            'custom_demo': {
                'id': 'custom_demo',
                'name': 'آزمایشی',
                'mode': 'light',
                'colors': {'bg': '#EEF2FF', 'panel': '#FFFFFF', 'text': '#1E1B4B', 'accent': '#4F46E5'},
                'tokens': {'radius': 22, 'glass_alpha': 80, 'bg_gradient': 'linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)'},
            }
        }
        self.win.data['settings']['section_themes'] = {'home': 'custom_demo'}
        rv.appearance.publish()
        self.wait_js(page, "getComputedStyle(document.documentElement).getPropertyValue('--card-radius').trim() === '22px'")
        self.wait_js(page, "getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim().toUpperCase() === '#4F46E5'")
        self.win.data['settings']['section_themes'] = {}
        rv.appearance.publish()

        # Switch main theme preset to 'bento_grid', verify main top bar LiquidNavEffect + LiquidThemeToggle + AI Daily Briefing + HomeLayoutEditor safety
        from appearance import apply_appearance, apply_section_appearances
        from settings_ui import SettingsDialog
        self.win.data['settings']['theme_preset'] = 'bento_grid'
        apply_appearance(self.win.data['settings'])
        self.win.sidebar.apply()
        self.win.refresh()
        apply_section_appearances(self.win)
        self.wait_js(page, "document.querySelector('[data-bento-grid=\"true\"]') !== null")
        self.assertTrue(self.win.theme_header.isVisible())
        self.wait_js(page, "document.querySelector('[data-ai-briefing=\"true\"]') !== null && !document.body.innerText.includes('دسترسی سریع بخش')")
        self.win.theme_header_mode.click()
        self.wait_js(page, "document.documentElement.classList.contains('dark')")
        self.win.theme_header_mode.click()
        self.wait_js(page, "!document.documentElement.classList.contains('dark')")

        # Verify opening HomeLayoutEditor from SettingsDialog switches stack safely and restores React Home on cancel
        dlg = SettingsDialog(self.win)
        dlg.open_home_editor()
        self.pump(lambda: getattr(self.win.home, 'home_editor', None) is not None and self.win.home.home_editor.isVisible(), timeout=5.0)
        self.win.home.home_editor.cancel()
        self.assertIs(self.win.home._react_stack.currentWidget(), rv)

        # Restore default theme
        self.win.data['settings']['theme_preset'] = 'default'
        apply_appearance(self.win.data['settings'])
        self.win.sidebar.apply()
        self.win.refresh()
        apply_section_appearances(self.win)
        self.wait_js(page, "document.querySelector('[data-bento-grid=\"true\"]') === null")

        # Verify permission check blocks forbidden bridge action
        responses = []
        rv.bridge.completed.connect(lambda req_id, raw: responses.append((req_id, raw)))
        rv.bridge.request('r-bad-mod', 'open_module', '{"key":"nonexistent_mod"}')
        self.pump(lambda: len(responses) >= 1, timeout=5.0)
        self.assertIn('"ok": false', responses[-1][1].lower())

    def test_calendar_react_view_event_manager_jalali_e2e(self):
        from storage import jformat, today_j
        self.win.tabs.setCurrentWidget(self.win.calendar_page)
        self.pump(lambda: getattr(self.win.calendar_page, 'react_view', None) is not None, timeout=10.0)
        rv = self.win.calendar_page.react_view
        page = rv.page

        self.wait_js(page, "document.querySelector('[data-calendar-view=\"true\"]') !== null && document.body.innerText.includes('مدیریت رویدادها')")
        self.assertIn('calendar.html', page.url().toString())

        # Create a real event through React bridge / EventManager UI
        before_count = len(self.win.events)
        today_str = jformat(today_j())
        rv.bridge.request('cal-create', 'create_event', json.dumps({
            'title': 'آزمایش تقویم هوشمند',
            'date_jalali': today_str,
            'company': 'مانا',
            'category': 'مالیات',
            'color': 'sky',
            'notes': 'ثبت شده از EventManager',
        }, ensure_ascii=False))
        self.pump(lambda: len(self.win.events) == before_count + 1, timeout=6.0)
        self.wait_js(page, "document.body.innerText.includes('آزمایش تقویم هوشمند')")

        # Switch to List view in React and toggle completion
        self.eval_js(
            page,
            """(() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'فهرست');
                btn && btn.click();
            })()""",
        )
        self.wait_js(page, "document.body.innerText.includes('فهرست رویدادها')")

        created_id = self.win.events[-1]['id']
        rv.bridge.request('cal-done', 'toggle_done', json.dumps({'id': created_id, 'done': True, 'date_jalali': today_str}))
        self.pump(lambda: self.win.events[-1].get('done') is True, timeout=5.0)

        rv.bridge.request('cal-del', 'delete_event', json.dumps({'id': created_id}))
        self.pump(lambda: len(self.win.events) == before_count, timeout=5.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)

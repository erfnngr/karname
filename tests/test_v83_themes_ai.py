import os,sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QPixmap
from appearance import LIGHT,DARK,palette_for,contrast,accent_foreground,apply_appearance,init_font
from assistant_model import GEMMA_MODEL
from theme_catalog import THEMES
from brand import dark_variant
import test_v6_ui as fixtures
from test_lmstudio import FakeLM
from lmstudio_client import LMClient
from org_store import DomainError

class PaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_all_requested_themes_have_readable_day_and_night_surfaces(self):
        self.assertEqual([row[0] for row in THEMES],['default','emerald_ivory','glass_mist','violet_modular','bento_grid'])
        for key,_,_ in THEMES:
            for mode in ('light','dark'):
                c=palette_for({'theme':mode,'theme_preset':key})
                for foreground,background in [('text','bg'),('text','panel'),('text','button'),('text','field'),('muted','bg'),('muted','panel')]:
                    with self.subTest(key=key,mode=mode,colors=(foreground,background)):
                        self.assertGreaterEqual(contrast(c[foreground],c[background]),4.5)
                self.assertGreaterEqual(contrast(accent_foreground(c['accent']),c['accent']),4.5)
        self.assertEqual(palette_for({'theme':'light'}),LIGHT)
        self.assertEqual(palette_for({'theme':'dark'}),DARK)
        self.assertNotEqual(palette_for({'theme_preset':'violet_modular'})['accent'],palette_for({'theme_preset':'glass_mist'})['accent'])
    def test_dark_logos_have_transparency_and_leave_original_intact(self):
        for name in ('karname.png','mana.jpg','arka.jpg'):
            original=QPixmap(str(Path(__file__).resolve().parents[1]/'assets'/name));before=original.toImage().pixelColor(0,0).alpha();dark=dark_variant(original)
            self.assertFalse(dark.isNull());self.assertEqual(dark.toImage().pixelColor(0,0).alpha(),0);self.assertEqual(original.toImage().pixelColor(0,0).alpha(),before)
    def test_supplied_iransans_is_registered(self):
        init_font();self.assertIn('IRANSans',QFontDatabase.families())

class PresetUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_settings_persist_preset_and_font_then_toggle_keeps_preset(self):
        from settings_ui import SettingsDialog
        from navigation_shortcuts import toggle_theme
        import storage
        dialog=SettingsDialog(self.win);dialog.show();self.pump()
        self.assertEqual(dialog.theme_preset.count(),5)
        dialog.theme_preset.setCurrentIndex(dialog.theme_preset.findData('violet_modular'))
        dialog.font.setCurrentIndex(dialog.font.findData('IRANSans'))
        values=dialog.values();self.assertEqual(values['theme_preset'],'violet_modular');self.assertEqual(values['font_family'],'IRANSans');self.assertEqual(values['theme'],'light')
        self.win.data['settings']=values;self.win.persist();apply_appearance(values)
        self.assertTrue(toggle_theme(self.win));self.assertEqual(self.win.data['settings']['theme'],'dark');self.assertEqual(self.win.data['settings']['theme_preset'],'violet_modular')
        loaded=storage.load_data()['settings'];self.assertEqual(loaded['theme_preset'],'violet_modular');self.assertEqual(loaded['font_family'],'IRANSans');self.assertEqual(loaded['theme'],'dark')
        self.assertTrue(toggle_theme(self.win));self.assertEqual(self.win.data['settings']['theme'],'light');dialog.deleteLater()
    def test_settings_search_filters_categories(self):
        from settings_ui import SettingsDialog
        from PySide6.QtWidgets import QLineEdit,QListWidget
        dialog=SettingsDialog(self.win);search=next(w for w in dialog.findChildren(QLineEdit) if w.placeholderText()=='جستجوی تنظیمات');search.setText('چاپ فاکتور');self.app.processEvents()
        lists=dialog.findChildren(QListWidget);nav=next(w for w in lists if any(w.item(i).text()=='چاپ فاکتور' for i in range(w.count())))
        visible=[nav.item(i).text() for i in range(nav.count()) if not nav.item(i).isHidden()];self.assertEqual(visible,['چاپ فاکتور']);dialog.deleteLater()
    def test_check_reminder_settings_are_editable(self):
        from settings_ui import SettingsDialog
        dialog=SettingsDialog(self.win);dialog.check_enabled.setChecked(False);dialog.check_days.setText('7, 2, 0');values=dialog.values();self.assertFalse(values['check_reminders']);self.assertEqual(values['check_lead_days'],[7,2,0]);dialog.deleteLater()
    def test_dark_home_and_calendar_render_when_theme_changes(self):
        for preset in ('emerald_ivory','glass_mist','violet_modular','bento_grid'):
            for mode in ('light','dark'):
                self.win.data['settings'].update(theme=mode,theme_preset=preset)
                apply_appearance(self.win.data['settings']);self.win.refresh();self.win.tabs.setCurrentWidget(self.win.home);self.app.processEvents()
                self.assertFalse(self.win.home.grab().isNull(),(preset,mode))
                self.win.tabs.setCurrentWidget(self.win.calendar_page);self.app.processEvents();self.assertFalse(self.win.calendar_page.grab().isNull(),(preset,mode))

class GemmaPolicy(unittest.TestCase):
    def test_saved_other_models_do_not_override_gemma(self):
        from types import SimpleNamespace
        from ai_chat_ui import connection
        with patch('lan_discovery.load_profile',return_value=None):
            for saved in ('bonsai2','other', ''):
                owner=SimpleNamespace(data={'settings':{'lmstudio':{'model':saved}}},base_dir=None)
                self.assertEqual(connection(owner)['model'],GEMMA_MODEL)
    def test_company_gateway_returns_only_gemma_and_rejects_other_models(self):
        import tempfile
        from org_store import Store
        from org_http import RunningServer
        from org_client import Client
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder);store.bootstrap('admin','pw','مدیر');server=RunningServer(folder,'127.0.0.1',0);client=Client('http://127.0.0.1:'+str(server.port));client.login('admin','pw')
            fake=ThreadingHTTPServer(('127.0.0.1',0),FakeLM);threading.Thread(target=fake.serve_forever,daemon=True).start();server.server.ai_backend='http://127.0.0.1:'+str(fake.server_port)+'/v1';FakeLM.requests=[];FakeLM.mode='stream'
            try:
                model_client=LMClient.company(client,3)
                try:
                    with patch('lmstudio_client.LMClient.models',return_value=['bonsai2',GEMMA_MODEL,'other']):
                        self.assertEqual(client.request('ai/models')['data'],[{'id':GEMMA_MODEL,'object':'model'}])
                    with self.assertRaises(DomainError):client.request('ai/chat/completions',dict(model='bonsai2',messages=[dict(role='user',content='hello')]))
                    self.assertEqual(FakeLM.requests,[])
                    self.assertEqual(model_client.chat(GEMMA_MODEL,[dict(role='user',content='سلام')],lambda _:None),'سلام از مدل محلی')
                    self.assertEqual(FakeLM.requests[-1]['model'],GEMMA_MODEL)
                finally:model_client.close()
            finally:client.session.close();server.close();fake.shutdown();fake.server_close()

if __name__=='__main__':unittest.main(verbosity=2)

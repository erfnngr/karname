import os,sys,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication,QFrame,QPushButton,QLabel
from appearance import apply_appearance
from theme_catalog import THEMES
from theme_dashboard import LAYOUTS
import test_v6_ui as fixtures

class ThemeLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def set_theme(self,key,mode='light'):
        self.win.tabs.setCurrentWidget(self.win.home);self.app.processEvents();self.win.data['settings'].update(theme=mode,theme_preset=key);apply_appearance(self.win.data['settings']);self.win.refresh();self.win.sidebar.apply();self.win.tabs.setCurrentWidget(self.win.home);self.app.processEvents()
    def test_distinct_layouts_no_visible_overlap_and_legacy_restores(self):
        self.win.data['settings']['weather_enabled']=False
        for width,height in [(1366,768),(1024,700)]:
            self.win.resize(width,height)
            for key,_,_ in THEMES[1:]:
                with self.subTest(size=(width,height),theme=key):
                    self.set_theme(key,'dark' if key in ('glass_night','emerald_neon') else 'light')
                    board=self.win.home.theme_dashboard
                    from PySide6.QtWidgets import QScrollArea
                    self.assertFalse([x for x in board.findChildren(QScrollArea) if x.isVisible()],'The home dashboard must not scroll.');self.assertFalse(hasattr(self.win,'theme_nav_more'))
                    cards=[x for x in board.findChildren(QFrame,'DashboardCard') if x.isVisible()]
                    self.assertEqual(len(cards),{'emerald_ivory':5,'glass_mist':5,'violet_modular':6,'bento_grid':5}[key],(self.win.isVisible(),self.win.home.isVisible(),board.isVisible(),board.isHidden(),self.win.tabs.currentWidget() is self.win.home,[(x.isVisible(),x.isHidden()) for x in board.findChildren(QFrame,'DashboardCard')]))
                    self.assertEqual(self.win.theme_nav.isVisible(),key!='emerald_ivory')
                    for i,a in enumerate(cards):
                        rect_a=a.rect().translated(a.mapTo(board,a.rect().topLeft()))
                        self.assertTrue(board.rect().contains(rect_a),(key,board.rect(),rect_a))
                        for b in cards[i+1:]:
                            if a.isAncestorOf(b) or b.isAncestorOf(a):continue
                            rect_b=b.rect().translated(b.mapTo(board,b.rect().topLeft()))
                            self.assertFalse(rect_a.intersects(rect_b),(key,rect_a,rect_b))
                    for label in board.findChildren(QLabel):
                        if label.isVisible() and label.text() and not label.wordWrap():self.assertLessEqual(label.fontMetrics().horizontalAdvance(label.text()),label.width()+2,label.text())
        self.set_theme('default');self.assertFalse(self.win.home.theme_dashboard.isVisible());self.assertFalse(self.win.theme_nav.isVisible());self.assertTrue(self.win.sidebar.sidebar.isVisible())
    def test_navigation_and_calendar_open_real_sections(self):
        self.set_theme('violet_modular');self.assertIs(self.win.theme_nav_buttons['calendar'].menu(),self.win.calendar_menu);self.assertIs(self.win.theme_nav_buttons['services'].menu(),self.win.services_menu);self.assertIs(self.win.theme_nav_buttons['desk'].menu(),self.win.desk_menu);self.assertTrue(self.win.theme_nav_buttons['month'].isHidden());self.assertTrue(self.win.month_action.isVisible());self.win.month_action.trigger();self.assertIs(self.win.tabs.currentWidget(),self.win.overview);self.assertTrue(self.win.nav_buttons['news'].isHidden());self.assertTrue(self.win.news_action.isVisible());self.win.news_action.trigger();self.assertIs(self.win.tabs.currentWidget(),self.win.news_panel);self.assertTrue(self.win.calculation_action.isVisible());self.win.calculation_action.trigger();self.assertIs(self.win.tabs.currentWidget(),self.win.calculation_page);self.assertTrue(self.win.attendance_action.isVisible());self.win.attendance_action.trigger();self.assertIs(self.win.tabs.currentWidget(),self.win.attendance)
        self.win.tabs.setCurrentWidget(self.win.home);self.app.processEvents();board=self.win.home.theme_dashboard;days=[b for b in board.findChildren(QPushButton,'DashboardDay') if b.isVisible()];self.assertTrue(days);days[0].click();self.assertIs(self.win.tabs.currentWidget(),self.win.calendar_page);self.assertEqual(self.win.selected.day,1)
    def test_compact_header_contains_every_permitted_destination(self):
        for width,height in ((800,520),(1024,700),(1366,768)):
            self.win.resize(width,height);self.set_theme('glass_mist');self.app.processEvents()
            strip=self.win.theme_nav;view=strip.viewport().rect()
            items=[b for b in self.win.theme_nav_buttons.values() if not b.isHidden()]
            self.assertTrue(items)
            for button in items:
                r=button.rect().translated(button.mapTo(strip.viewport(),button.rect().topLeft()))
                self.assertTrue(view.contains(r),(width,button.accessibleName(),view,r))
                self.assertTrue(button.accessibleName());self.assertTrue(button.toolTip())
            self.assertEqual(strip.horizontalScrollBar().maximum(),0)
            board=self.win.home.theme_dashboard
            for name in ('Greeting','DashboardQuote'):
                label=next(x for x in board.findChildren(QLabel,name) if x.isVisible());r=label.rect().translated(label.mapTo(board,label.rect().topLeft()));self.assertGreaterEqual(r.height(),label.fontMetrics().height());self.assertTrue(board.rect().contains(r),(name,board.rect(),r))
    def test_forecast_fits_home_in_light_and_dark(self):
        from test_weather import samples
        from weather import parse_forecast
        now,payload=samples();service=self.win.home.weather_service;service.timer.stop();service.data=parse_forecast(payload,now);service.checked_at=now;service.busy=False;service.error=''
        self.win.resize(1024,700)
        for mode in ('light','dark'):
            with self.subTest(mode=mode):
                self.set_theme('glass_mist',mode);board=self.win.home.theme_dashboard;strip=next(x for x in board.findChildren(QFrame,'WeatherStrip') if x.isVisible());rect=strip.rect().translated(strip.mapTo(board,strip.rect().topLeft()));self.assertTrue(board.rect().contains(rect));self.assertFalse(any('Visual Crossing' in x.text() or '7Timer' in x.text() for x in strip.findChildren(QLabel)));self.assertIn('آب‌وهوا',strip.title.text())
    def test_group_menus_stay_available_when_only_child_is_permitted(self):
        from main_ui import apply_preferences
        self.set_theme('glass_mist');prefs=self.win.data.setdefault('preferences',{});prefs['visible_modules']=['home','month','calculation','news','attendance'];prefs['preferences_schema']=11;apply_preferences(self.win);self.app.processEvents()
        self.assertFalse(self.win.nav_buttons['calendar'].isHidden());self.assertFalse(self.win.nav_buttons['services'].isHidden());self.assertFalse(self.win.nav_buttons['desk'].isHidden())
        self.assertTrue(self.win.month_action.isVisible());self.assertTrue(self.win.calculation_action.isVisible());self.assertFalse(self.win.calendar_action.isVisible());self.assertTrue(self.win.news_action.isVisible());self.assertFalse(self.win.services_action.isVisible());self.assertTrue(self.win.attendance_action.isVisible());self.assertFalse(self.win.desk_action.isVisible())
    def test_hidden_module_stays_hidden_in_new_navigation(self):
        from main_ui import apply_preferences
        self.set_theme('glass_mist');self.win.data.setdefault('preferences',{})['visible_modules']=['home','calendar'];self.win.data['preferences']['preferences_schema']=11;apply_preferences(self.win);self.app.processEvents();self.assertTrue(self.win.theme_nav_buttons['news'].isHidden());self.assertFalse(self.win.news_action.isVisible());self.assertFalse(self.win.theme_nav_buttons['home'].isHidden())

if __name__=='__main__':unittest.main(verbosity=2)

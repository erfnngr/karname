import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication,QFrame,QPushButton,QLabel
from appearance import apply_appearance
from theme_catalog import THEMES,preset
from storage import today_j
import test_v6_ui as fixtures

class ReferenceThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_custom_widget_sizes_and_order(self):
        self.win.data.setdefault('preferences',{}).update(home_widgets=['calendar','summary'],home_widget_sizes={'calendar':2,'summary':1})
        self.theme('glass_mist');board=self.win.home.theme_dashboard
        from PySide6.QtWidgets import QGridLayout
        grids=board.findChildren(QGridLayout)
        grid=next(g for g in grids if g.count()>=2 and g.getItemPosition(0)[3]==2)
        self.assertEqual(grid.getItemPosition(1)[:2],(0,2))
    def theme(self,key,mode='light'):
        self.win.resize(1366,768);self.win.tabs.setCurrentWidget(self.win.home);self.win.data['settings'].update(theme_preset=key,theme=mode);apply_appearance(self.win.data['settings']);self.win.refresh();self.win.sidebar.apply();self.app.processEvents()
    def card(self,name):
        board=self.win.home.theme_dashboard
        for frame in board.findChildren(QFrame,'DashboardCard'):
            if not frame.isVisible():continue
            labels=frame.findChildren(QLabel,'DashboardTitle');buttons=frame.findChildren(QPushButton,'CalendarTitle')
            if labels and labels[0].text()==name or name=='calendar' and buttons:return frame
        self.fail('Card not found: '+name)
    def x(self,w):return w.mapTo(self.win.home.theme_dashboard,w.rect().topLeft()).x()
    def test_exactly_three_reference_themes_plus_default(self):
        self.assertEqual([r[0] for r in THEMES],['default','emerald_ivory','glass_mist','violet_modular','bento_grid']);self.assertEqual(preset('blue_cloud'),'default')
        from settings_ui import SettingsDialog
        d=SettingsDialog(self.win);d.show();self.pump();self.assertEqual(d.theme_preset.count(),5);d.close();d.deleteLater();self.app.processEvents()
    def test_three_different_reference_layouts(self):
        self.win.data['settings']['weather_enabled']=False
        self.theme('emerald_ivory');self.assertTrue(self.win.sidebar.sidebar.isVisible());self.assertLess(self.x(self.card('یادآورهای امروز')),self.x(self.card('calendar')))
        self.theme('glass_mist');self.assertTrue(self.win.theme_header.isVisible());self.assertLess(self.x(self.card('یادآورهای امروز')),self.x(self.card('calendar')));self.assertLess(self.x(self.card('calendar')),self.x(self.card('ساعات کاری')))
        self.theme('violet_modular');self.assertLess(self.x(self.card('calendar')),self.x(self.card('ساعات کاری')));self.assertLess(self.x(self.card('ساعات کاری')),self.x(self.card('برنامه کاری امروز')))
    def test_calendar_controls_and_violet_calendar_reposition(self):
        self.theme('violet_modular');board=self.win.home.theme_dashboard;old=(board.view_year,board.view_month);arrow=next(b for b in board.findChildren(QPushButton,'CalendarArrow') if b.isVisible() and b.accessibleName()=='ماه بعد');arrow.click();self.app.processEvents();self.assertNotEqual((board.view_year,board.view_month),old)
        day=next(b for b in board.findChildren(QPushButton,'DashboardDay') if b.isVisible());day.click();self.app.processEvents();self.assertIs(self.win.tabs.currentWidget(),self.win.calendar_page);self.win.sidebar.apply();self.app.processEvents();self.assertLess(self.win.calendar_shell.mapTo(self.win.calendar_page,self.win.calendar_shell.rect().topLeft()).x(),self.win.calendar_side.mapTo(self.win.calendar_page,self.win.calendar_side.rect().topLeft()).x())
    def test_charts_use_real_selected_attendance_and_current_month_tasks(self):
        self.theme('violet_modular');from theme_dashboard import AttendanceChart
        self.win.attendance.report={'days':[{'date':'1405/08/01','worked_minutes':480,'entries':[{'check_in':'09:00'}]},{'date':'1405/08/02','worked_minutes':300,'entries':[{'check_in':'09:00'}]}]}
        for variant in ('line','bars'):
            w=AttendanceChart(self.win,variant);w.resize(300,140);self.assertFalse(w.grab().isNull());w.deleteLater()
        now=today_j();due=f'{now.year:04d}/{now.month:02d}/01';self.win.workspace.snapshot={'tasks':[{'payload':{'due_date':due,'status':'completed'}},{'payload':{'due_date':due,'status':'draft'}},{'payload':{'due_date':'1300/01/01','status':'completed'}}]};self.assertEqual(self.win.home.theme_dashboard.counts(),(1,1))
    def test_several_real_reminders_fit_on_small_home(self):
        from storage import new_event,jformat,today_j
        self.win.resize(1024,700);self.win.events[:]=[new_event('شخصی','نمونه '+str(i),jformat(today_j())) for i in range(7)]
        for key in ('emerald_ivory','glass_mist','violet_modular','bento_grid'):
            self.win.data['settings'].update(theme_preset=key,theme='light');apply_appearance(self.win.data['settings']);self.win.refresh();self.win.sidebar.apply();self.win.tabs.setCurrentWidget(self.win.home);self.app.processEvents();board=self.win.home.theme_dashboard
            for frame in board.findChildren(QFrame,'DashboardCard'):
                if frame.isVisible():
                    rect=frame.rect().translated(frame.mapTo(board,frame.rect().topLeft()));self.assertTrue(board.rect().contains(rect),(key,rect,board.rect()))
    def test_grouped_sections_keep_keyboard_shortcuts(self):
        from navigation_shortcuts import activate
        self.theme('glass_mist')
        for key in ('month','calculation','news','attendance'):
            self.assertTrue(activate(self.win,key),key);self.assertIs(self.win.tabs.currentWidget(),self.win.modules[key])
    def test_removed_preset_falls_back_to_default_shell(self):
        self.theme('blue_cloud');self.assertTrue(self.win.sidebar.sidebar.isVisible());self.assertFalse(self.win.theme_header.isVisible());self.assertTrue(not hasattr(self.win.home,'theme_dashboard') or not self.win.home.theme_dashboard.isVisible())

if __name__=='__main__':unittest.main(verbosity=2)

import sys,os,unittest,tempfile,copy,json
from pathlib import Path
from datetime import datetime,date,timedelta,timezone
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['QT_QPA_PLATFORM']='offscreen'
from news_dates import parse_publication,publication_from_page,recent,prune_news,TEHRAN

class PublicationTests(unittest.TestCase):
    def test_exact_fourteen_day_window(self):
        now=datetime(2026,10,26,12,tzinfo=timezone.utc)
        for delta,expected in [(timedelta(days=14),True),(timedelta(days=14,seconds=1),False),(timedelta(),True),(timedelta(seconds=-1),False)]:
            self.assertEqual(recent({'published_at':(now-delta).isoformat()},now),expected)
        self.assertFalse(recent({'first_seen':now.isoformat()},now))
        self.assertFalse(recent({'modified_at':now.isoformat()},now))
    def test_jalali_farsi_and_rfc_dates(self):
        self.assertEqual(parse_publication('زمان انتشار: ۲۹ مهر ۱۴۰۵ - ساعت ۲۱:۲۶'),datetime(2026,10,21,21,26,tzinfo=TEHRAN))
        self.assertEqual(parse_publication('۱۴۰۵/۰۸/۰۴').date(),date(2026,10,26))
        self.assertEqual(parse_publication('Mon, 26 Oct 2026 05:00:00 GMT').hour,5)
        self.assertIsNone(parse_publication('1405/12/31'))
    def test_published_never_modified_or_body_deadline(self):
        self.assertIsNone(publication_from_page('<meta property="article:modified_time" content="2026-10-26"><p>موعد: ۱۴۰۵/۰۸/۰۴</p>'))
        page='<span class="text-muted">زمان انتشار: 29 مهر 1405 - ساعت 21:26</span><span>زمان بروز رسانی: 3 آبان 1405</span>'
        self.assertEqual(publication_from_page(page).date(),date(2026,10,21))
        self.assertEqual(publication_from_page('<script type="application/ld+json">{"@graph":[{"dateModified":"2026-10-26","datePublished":"2026-10-20"}]}</script>').date(),date(2026,10,20))
    def test_offline_prune_and_legacy_sources(self):
        now=datetime(2026,10,26,tzinfo=timezone.utc)
        state={'items':[{'id':'new','published_at':'2026-10-25'},{'id':'old','published_at':'2026-09-26'},{'id':'unknown','first_seen':now.isoformat()}]}
        self.assertEqual(prune_news(state,now),2);self.assertEqual(state['items'][0]['id'],'new')
        from official_news import get_sources
        old={'news_sources':[dict(id='tax',name='tax',url='https://tax.gov.ir/action/do/show/409',enabled=False),dict(id='mine',name='mine',url='https://example.com/news')]}
        new=get_sources(old)
        self.assertIn('intamedia.ir',new[0]['url']);self.assertFalse(new[0]['enabled']);self.assertTrue(new[0]['official']);self.assertEqual(new[1]['url'],old['news_sources'][1]['url'])
        self.assertTrue(any(x['id']=='tax-announcements' for x in new))
    def test_browser_challenge_is_not_successful_news(self):
        from official_news import download
        response=MagicMock();response.is_redirect=False;response.status_code=200;response.headers={'Content-Type':'text/html'}
        response.iter_content.return_value=[b'<html>Transferring to the website...</html>'];response.__enter__.return_value=response
        with patch('official_news.requests.get',return_value=response):
            with self.assertRaisesRegex(ValueError,'بررسی مرورگر'):download('https://tamin.ir/','tamin.ir')

class ScheduleAndCalendarTests(unittest.TestCase):
    def test_no_overdue_even_with_legacy_switch(self):
        import storage,jdatetime
        from reminders import due_reminders
        today=date(2026,10,26);ev=storage.new_event('مانا','بیمه',storage.jformat(jdatetime.date.fromgregorian(date=today-timedelta(days=1))))
        self.assertFalse(due_reminders([ev],dict(storage.DEFAULT_SETTINGS,overdue_reminders=True),today))
    def test_movable_1405_and_fixed_future_holidays(self):
        import jdatetime
        from iran_calendar import day_off,iran_on_date
        ashura=jdatetime.date(1405,4,4).togregorian()
        self.assertTrue(any(x['title']=='عاشورا' and x['holiday'] for x in iran_on_date(ashura)))
        self.assertTrue(day_off(ashura));self.assertTrue(day_off(date(2026,10,29)));self.assertTrue(day_off(date(2026,10,30)))
        self.assertTrue(any(x['holiday'] for x in iran_on_date(jdatetime.date(1425,1,1).togregorian())))
        self.assertFalse(any(x['title']=='عاشورا' for x in iran_on_date(jdatetime.date(1406,4,4).togregorian())))
    def test_ui_migration_saves_once_and_preserves_custom_values(self):
        import storage
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':folder}):
            d=storage.load_data();d.pop('ui_version');d['settings'].update(monthly_summary=True,overdue_reminders=True,font_size=16);d['events'][0]['notes']='custom edit';storage.save_data(d)
            upgraded=storage.load_data();self.assertEqual(upgraded['ui_version'],4);self.assertEqual(upgraded['settings']['font_size'],16);self.assertEqual(upgraded['events'][0]['notes'],'custom edit')
            self.assertFalse(upgraded['settings']['monthly_summary']);self.assertFalse(upgraded['settings']['overdue_reminders'])
            self.assertTrue((Path(folder)/'calendar-before-v4.json').exists());self.assertEqual(json.loads(storage.data_path().read_text(encoding='utf-8'))['ui_version'],4)

class V4UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':self.temp.name});self.env.start()
        import storage
        d=storage.load_data();d['settings'].update(news_enabled=False,reminder_enabled=False);storage.save_data(d)
        from app import TaxWindow
        self.win=TaxWindow();self.win.timer.stop();self.win.news_panel.timer.stop()
    def tearDown(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        if self.win.tray:self.win.tray.hide()
        self.win.hide();self.win.deleteLater();self.app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.env.stop();self.temp.cleanup()
    def test_pickers_and_edit_delete_location(self):
        from karname_ui import QuickPicker,CompactRow
        from PySide6.QtWidgets import QPushButton
        from app import EventDialog
        year=QuickPicker(self.win,'year');self.assertEqual(year.grid.count(),9);year.page(9);self.assertEqual(year.grid.count(),9);year.choose(1415);self.assertEqual(year.value,1415)
        month=QuickPicker(self.win,'month');self.assertEqual(month.grid.count(),12)
        row=CompactRow(self.win,self.win.events[0]);self.assertEqual([b.text() for b in row.findChildren(QPushButton)],['ویرایش'])
        dialog=EventDialog(self.win,self.win.data['companies'],self.win.events[0]);self.assertTrue(any(b.text()=='حذف یادآور' for b in dialog.findChildren(QPushButton)))
        dialog.request_delete();self.assertTrue(dialog.delete_requested)
    def test_colors_remain_readable_at_extreme_intensities(self):
        from brand import row_colors,popup_style
        from appearance import contrast
        import storage
        for theme in ('light','dark'):
            for color in ('#FFFFFF','#000000','#00FF00','#FFFF00','#0000FF'):
                for opacity in (5,18,100):
                    s=dict(storage.DEFAULT_SETTINGS,theme=theme,event_tax_color=color,event_tax_opacity=opacity,mana_popup_color=color)
                    bg,fg,_=row_colors({'reminder_group':'default','title':'مالیات'},s);self.assertGreaterEqual(contrast(fg,bg),4.5)
                    popup,_=popup_style('مانا',s);self.assertGreaterEqual(contrast(popup['popup_fg'],popup['popup_bg']),4.5)
    def test_company_popups_scheduled_and_deduplicated(self):
        from storage import new_event,jformat,today_j
        self.win.data['settings']['reminder_enabled']=True
        self.win.events=[new_event(company,'تکلیف',jformat(today_j())) for company in ('مانا','آرکا','شخصی')]
        with patch.object(self.win,'popup') as popup:
            self.win.check_alerts();self.assertEqual(popup.call_count,3);self.assertEqual({c.kwargs['company'] for c in popup.call_args_list},{'مانا','آرکا',None})
            self.win.check_alerts();self.assertEqual(popup.call_count,3)
            self.win.first_notification();self.assertEqual(popup.call_count,3)
    def test_home_position_color_wheel_and_five_second_preview(self):
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtCore import Qt
        from color_wheel import ColorWheelDialog
        from settings_ui import SettingsDialog
        self.win.resize(1024,700);self.win.show();self.app.processEvents();self.assertIs(self.win.tabs.currentWidget(),self.win.home)
        self.assertLess(self.win.home.side.x(),self.win.home.width()/2)
        gear=next(b for b in self.win.findChildren(QToolButton) if b.accessibleName()=='تنظیمات');self.assertLess(gear.x(),100)
        wheel=ColorWheelDialog('#26B67B',self.win);wheel.hex.setText('#ff00ff');wheel.from_hex();self.assertEqual(wheel.color.name(),'#ff00ff');self.assertEqual(wheel.wheel.color.name(),'#ff00ff')
        settings=SettingsDialog(self.win);settings.seconds.setValue(15)
        with patch.object(self.win,'popup') as popup:
            settings.preview();self.assertEqual(popup.call_args.kwargs['settings']['popup_seconds'],5)
    def test_news_scroll_handle_never_overlaps_arrows(self):
        from PySide6.QtWidgets import QScrollArea,QStyle,QStyleOptionSlider
        self.win.tabs.setCurrentWidget(self.win.news_panel)
        stamp=datetime.now(timezone.utc).isoformat();self.win.news_panel.state['items']=[dict(id=str(i),source_id='tax',source='tax',title='خبر مالیات',url='https://www.intamedia.ir/',published_at=stamp,read=False,official=True) for i in range(40)]
        self.win.news_panel.render();self.win.resize(1024,700);self.win.show();self.app.processEvents()
        for area in self.win.news_panel.findChildren(QScrollArea):
            bar=area.verticalScrollBar()
            for position in (bar.minimum(),bar.maximum()//2,bar.maximum()):
                bar.setValue(position);opt=QStyleOptionSlider();bar.initStyleOption(opt)
                handle=bar.style().subControlRect(QStyle.CC_ScrollBar,opt,QStyle.SC_ScrollBarSlider,bar)
                for control in (QStyle.SC_ScrollBarSubLine,QStyle.SC_ScrollBarAddLine):
                    arrow=bar.style().subControlRect(QStyle.CC_ScrollBar,opt,control,bar);self.assertFalse(handle.intersects(arrow))

if __name__=='__main__':unittest.main(verbosity=2)

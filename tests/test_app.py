import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from datetime import datetime,timezone,timedelta,date

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
temp=tempfile.TemporaryDirectory()
os.environ['TAXCALENDAR_DATA_DIR']=temp.name
os.environ['QT_QPA_PLATFORM']='offscreen'
from penalties import calculate,number,get_rules
from official_news import SOURCES,extract,extract_feed,merge_news,download
TAX_SOURCE=dict(id='tax',name='سازمان امور مالیاتی',url='https://tax.gov.ir/action/do/show/409',domain='tax.gov.ir')

class RulesTests(unittest.TestCase):
    def test_insurance_and_units(self):
        r=calculate('۱۰۰٬۰۰۰٬۰۰۰','۱۰','۲','۳')
        self.assertEqual(r['penalty'],Decimal('16000000'))
        self.assertEqual(r['total'],Decimal('116000000'))
        self.assertEqual(calculate('10000000','10','2','3')['penalty']*10,r['penalty'])

    def test_disable_separate_components(self):
        self.assertEqual(calculate('100000','30','2.5','2',use_fixed=False)['penalty'],5000)
        self.assertEqual(calculate('100000','30','2.5','2',use_monthly=False)['penalty'],30000)
        self.assertEqual(calculate('100000','0','2.5','0.5')['penalty'],1250)

    def test_invalid_and_nonfinite(self):
        for n in ('-1','NaN','Infinity','bad','','1e99','-Infinity'):
            with self.subTest(n=n), self.assertRaises(ValueError):number(n)
        for args in [('1','101','2','3'),('1','2','101','3'),('1','2','3','1201')]:
            with self.assertRaises(ValueError):calculate(*args)

    def test_rate_persistence_isolated(self):
        rules=get_rules({'penalty_rules':{'insurance':{'fixed':'15'}}})
        self.assertEqual(rules[0]['fixed'],'15')
        self.assertEqual(get_rules({})[0]['fixed'],'10')
        self.assertEqual(next(r for r in rules if r['id']=='salary_list')['basis'],'حقوق پرداختی مشمول تخلف')

class NewsTests(unittest.TestCase):
    def test_duplicate_article_uses_one_short_title(self):
        page='<a href="/web/articles/view/1234/a">مالیات ارزش افزوده و توضیحات طولانی درباره قوانین</a><a href="/web/articles/view/1234/a">مالیات ارزش افزوده</a>'
        source=dict(id='heyva',name='test',url='https://www.heyvalaw.com/',domain='heyvalaw.com')
        result=extract(page,source);self.assertEqual(len(result),1);self.assertEqual(result[0]['title'],'مالیات ارزش افزوده')

    def test_editable_sources_validation(self):
        from official_news import get_sources,validate_source_url
        data={'news_sources':[dict(id='mine',name='خبر',url='https://example.com/news',enabled=False)]}
        source=get_sources(data)[0];self.assertFalse(source['enabled']);self.assertFalse(source['official'])
        for url in ['http://example.com','https://127.0.0.1','https://localhost','file:///test','https://user:pass@example.com']:
            with self.subTest(url=url),self.assertRaises(ValueError):validate_source_url(url)
    def test_official_rss_and_unsafe_xml(self):
        rss='<rss><channel><item><title>تمدید مهلت ارسال لیست بیمه اعلام شد</title><link>http://tamin.ir/news/item/123</link><pubDate>test</pubDate></item></channel></rss>'.encode()
        items=extract_feed(rss,SOURCES[1]);self.assertEqual(len(items),1)
        self.assertEqual(items[0]['url'],'https://tamin.ir/news/item/123')
        with self.assertRaises(ValueError):extract_feed(b'<!DOCTYPE rss><rss/>',SOURCES[1])
    def test_extract_only_official_relevant_news(self):
        page='''<html><a href="/action/do/show/999">تمدید مهلت ارسال اظهارنامه ارزش افزوده اعلام شد</a>
        <a href="https://evil.example/news/1">تمدید مهلت ارسال اظهارنامه ارزش افزوده اعلام شد</a>
        <a href="/action/do/show/888">مسابقه ورزشی کارکنان برگزار شد</a>
        <a href="https://my.tax.gov.ir/">ورود به خدمات ارسال اظهارنامه مالیاتی</a>
        <a href="/action/do/show/999">تمدید مهلت ارسال اظهارنامه ارزش افزوده اعلام شد</a></html>'''
        r=extract(page,TAX_SOURCE);self.assertEqual(len(r),1);self.assertTrue(r[0]['important'])

    def test_baseline_failure_reconnect_dedup(self):
        state={};item=dict(id='a',title='تمدید مهلت',url='https://tax.gov.ir/action/do/show/1',source='tax',source_id='tax',important=True,published_at=datetime.now(timezone.utc).isoformat())
        result=dict(source_id='tax',checked_at='2026-10-25T08:00:00+00:00',ok=True,items=[item],message='ok')
        self.assertEqual(merge_news(state,result),[])
        self.assertEqual(merge_news(state,result),[])
        merge_news(state,dict(result,ok=False,items=[],message='offline'))
        self.assertEqual(len(state['items']),1)
        self.assertTrue(state['sources']['tax']['last_success'])
        fresh=merge_news(state,dict(result,items=[dict(item,id='b')]))
        self.assertEqual(len(fresh),1)
        self.assertEqual(len(state['items']),2)

    def test_cross_domain_redirect_blocked_before_request(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.is_redirect=True;response.headers={'Location':'https://evil.example/'}
        response.__enter__.return_value=response
        with patch('official_news.requests.get',return_value=response) as request:
            with self.assertRaises(ValueError):download(TAX_SOURCE['url'],'tax.gov.ir')
            self.assertEqual(request.call_count,1)

class StorageTests(unittest.TestCase):
    def test_twenty_year_plan_preserves_originals_and_is_idempotent(self):
        import copy,storage
        from planning import extend_calendar
        seed=json.loads((ROOT/'data/initial_events.json').read_text(encoding='utf-8'))
        original=copy.deepcopy(seed['events']);extend_calendar(seed);self.assertEqual(seed['events'][:70],original)
        self.assertGreater(len(seed['events']),1300)
        self.assertEqual(extend_calendar(seed),0)
        future=[e for e in seed['events'] if e.get('generated')]
        self.assertTrue(any(e['date_jalali'].startswith('1425/') for e in future))
        self.assertEqual(len({e['id'] for e in seed['events']}),len(seed['events']))
        for event in future:storage.parse_j(event['date_jalali']);self.assertTrue(event['planning_only'])

class ReminderTests(unittest.TestCase):
    def test_every_requested_interval_and_dedup(self):
        import storage
        from datetime import date,timedelta
        from reminders import due_reminders,DEFAULT_LEADS
        settings=dict(storage.DEFAULT_SETTINGS);today=date(2026,10,25)
        for days in range(22):
            dt=today+timedelta(days=days)
            import jdatetime
            e=storage.new_event('test','test',storage.jformat(jdatetime.date.fromgregorian(date=dt)))
            items=due_reminders([e],settings,today)
            self.assertEqual(bool(items),days in DEFAULT_LEADS)
            if items:
                e['last_alerts'][items[0][3]]=True;self.assertFalse(due_reminders([e],settings,today))

    def test_separate_personal_custom_and_snooze(self):
        import storage,jdatetime
        from datetime import date,timedelta
        from reminders import due_reminders
        today=date(2026,10,25);settings=dict(storage.DEFAULT_SETTINGS,personal_lead_days=[8],default_lead_days=[20])
        e=storage.new_event('test','test',storage.jformat(jdatetime.date.fromgregorian(date=today+timedelta(days=8))))
        self.assertTrue(due_reminders([e],settings,today));e['reminder_group']='default';self.assertFalse(due_reminders([e],settings,today))
        e.update(reminder_custom=True,lead_days=[8]);self.assertTrue(due_reminders([e],settings,today))
        e['snooze_until']=(today+timedelta(days=1)).isoformat();self.assertFalse(due_reminders([e],settings,today))

class AppearanceTests(unittest.TestCase):
    def test_outlook_export_utf8_and_line_folding(self):
        from calendar_export import encode_ics
        data=encode_ics(['BEGIN:VCALENDAR','SUMMARY:'+'تکلیف مالیاتی '*30,'END:VCALENDAR'])
        self.assertNotIn(b'\r\r\n',data)
        self.assertTrue(all(len(line)<=75 for line in data.split(b'\r\n')))
        self.assertIn('تکلیف',data.decode('utf-8'))
    def test_all_primary_and_muted_colors_readable(self):
        from appearance import LIGHT,DARK,contrast
        for colors in (LIGHT,DARK):
            for bg in ('bg','panel','field','button','selected','today'):
                self.assertGreaterEqual(contrast(colors['text'],colors[bg]),4.5)
                self.assertGreaterEqual(contrast(colors['muted'],colors[bg]),4.5)

    def test_world_day_shifts_correctly_between_calendars(self):
        import jdatetime
        from occasions import on_date,for_month
        from datetime import date
        self.assertTrue(any('سازمان ملل' in x['title'] for x in on_date(date(2026,10,24))))
        for year in (1405,1408,1425):
            for month in range(1,13):
                for item in for_month(year,month):
                    jd=jdatetime.date.fromgregorian(date=item['date']);self.assertEqual((jd.year,jd.month),(year,month))
    def test_existing_data_and_backup_preserved(self):
        import storage
        data=storage.load_data()
        original_ids={e['id'] for e in json.loads((ROOT/'data/initial_events.json').read_text(encoding='utf-8'))['events']}
        retained=data['events']+[entry['event'] for key in ('source_duplicate_archive','company_defaults_archive') for entry in data.get(key,[])]
        self.assertTrue(original_ids.issubset({e['id'] for e in retained}))
        self.assertEqual(sum(bool(e['needs_review']) for e in data['events']),4)
        data['events'][0]['notes']='personal edit';storage.save_data(data)
        loaded=storage.load_data();self.assertEqual(loaded['events'][0]['notes'],'personal edit')
        self.assertTrue((Path(temp.name)/'calendar-backup.json').exists())

class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_tabs_filters_calculator_and_event_category(self):
        from app import TaxWindow,EventDialog
        win=TaxWindow();win.news_panel.timer.stop();win.timer.stop()
        win.news_panel.enabled.setChecked(False)
        for page in (win.home,win.calendar_page,win.desk,win.chat,win.workspace,win.attendance):self.assertGreaterEqual(win.tabs.indexOf(page),0)
        self.assertIs(win.tabs.currentWidget(),win.home)
        win.category_filter.setCurrentText('بیمه')
        self.assertTrue(all('بیمه' in ev['title'] for ev in win.events if win.filtered_company(ev)))
        calc=win.calculator;calc.amount.setText('100000000');calc.fixed.setText('10');calc.monthly.setText('2');calc.months.setText('3')
        self.assertIn('۱۶,۰۰۰,۰۰۰',calc.result.text())
        calc.save_rule()
        win.calculator.select_for_event({'title':'مالیات حقوق','notes':'test'})
        self.assertEqual(calc.kind.currentData(),'salary')
        dialog=EventDialog(win,win.data['companies']);dialog.title.setText('test');dialog.category.setCurrentText('بیمه');dialog.validate()
        self.assertEqual(dialog.payload['category'],'بیمه')
        win.mode_filter.setCurrentText('همه رویدادها');win.refresh();win.show_main();self.app.processEvents()
        self.assertTrue(win.isVisible())
        win.tray.hide() if win.tray else None
        win._exit_approved=True;win.close();win.deleteLater();self.app.processEvents()

    def test_theme_settings_fonts_and_popup_expiration(self):
        import storage
        from app import TaxWindow,StartupPopup
        from settings_ui import SettingsDialog
        from appearance import apply_appearance
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtTest import QTest
        win=TaxWindow();win.news_panel.enabled.setChecked(False);win.timer.stop();win.news_panel.timer.stop()
        self.assertIn('Vazirmatn',QFontDatabase.families())
        dialog=SettingsDialog(win);dialog.theme.setCurrentIndex(1);values=dialog.values();apply_appearance(values)
        self.assertEqual(values['theme'],'dark');self.assertEqual(values['popup_seconds'],5)
        dialog.validate();self.assertEqual(len(dialog.result_sources),6)
        win.data['news_sources']=dialog.result_sources;win.news_panel.reload_sources()
        popup=StartupPopup('آزمایش',dict(values,popup_seconds=1,popup_fade_ms=150));popup.show_popup();QTest.qWait(1200);self.assertFalse(popup.isVisible());popup.deleteLater()
        win.tray.hide() if win.tray else None
        win._exit_approved=True;win.close();win.deleteLater();self.app.processEvents();apply_appearance(storage.DEFAULT_SETTINGS)

if __name__=='__main__':
    unittest.main(verbosity=2)

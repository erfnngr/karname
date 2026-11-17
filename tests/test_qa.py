"""Regression and workflow tests found during the complete 4.1 QA pass."""
import os,sys,tempfile,json,unittest,copy
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.environ['QT_QPA_PLATFORM']='offscreen'
import storage,jdatetime
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QPushButton,QMessageBox,QFileDialog,QScrollArea
from PySide6.QtCore import QTimer,Qt,QCoreApplication,QEvent

class QaStorageTests(unittest.TestCase):
    def test_real_and_numeric_excel_dates(self):
        for value,expected in [('۱۴۰۵/۰۸/۰۴','1405/08/04'),(date(2026,10,26),'1405/08/04'),('تا ۲۴ آبان ۱۴۰۵','1405/08/24')]:
            self.assertEqual(storage.extract_jalali(value),(expected,''))
    def test_reimport_after_edit_preserves_existing(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'test.xlsx';book=Workbook();sheet=book.active;sheet.title='شرکت آزمایشی';sheet.append(['ماه','عنوان','سررسید','توضیح']);sheet.append(['آبان ۱۴۰۵','مالیات','پایان آذر ۱۴۰۵','notes']);guide=book.create_sheet('راهنمای مهلت‌ها');guide.append(['عنوان','توضیح']);guide.append(['نکته','راهنمای فایل']);book.save(file);book.close()
            d={'companies':[],'events':[]};self.assertEqual(storage.import_excel(file,d),(1,0));d['events'][0]['title']='ویرایش شخصی';d['events'][0]['notes']='حفظ شود';self.assertEqual(storage.import_excel(file,d),(0,0));self.assertEqual(d['events'][0]['notes'],'حفظ شود');self.assertEqual(d['companies'],['شرکت آزمایشی']);file.unlink()
    def test_reimport_does_not_restore_company_archived_tasks(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'test.xlsx';book=Workbook();sheet=book.active;sheet.title='آرکا';sheet.append(['ماه','عنوان','سررسید','توضیح']);sheet.append(['آبان ۱۴۰۵','مالیات حقوق','پایان آذر ۱۴۰۵','']);book.save(file);book.close()
            data={'companies':[],'events':[]};self.assertEqual(storage.import_excel(file,data),(1,0))
            archived=data['events'].pop();data['company_defaults_archive']=[{'event':archived}]
            self.assertEqual(storage.import_excel(file,data),(0,0));self.assertEqual(data['events'],[])
    def test_corrupt_json_recovers_valid_backup_without_losing_it(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':folder}):
            d=storage.load_data();d['events'][0]['notes']='پشتیبان سالم';storage.save_data(d);storage.save_data(d)
            backup=(Path(folder)/'calendar-backup.json').read_bytes();storage.data_path().write_text('{broken',encoding='utf-8')
            recovered=storage.load_data();self.assertEqual(recovered['events'][0]['notes'],'پشتیبان سالم');self.assertEqual((Path(folder)/'calendar-backup.json').read_bytes(),backup);self.assertTrue(list(Path(folder).glob('calendar-damaged-*.json')))
    def test_publication_time_datetime_attribute(self):
        from news_dates import publication_from_page
        self.assertEqual(publication_from_page('<time itemprop="datePublished" datetime="2026-10-25"></time>').date(),date(2026,10,25))
    def test_exact_excel_duplicates_are_archived_but_personal_twins_remain(self):
        from data_cleanup import archive_excel_duplicates
        event=storage.new_event('مانا','بیمه','1405/08/30');event.update(created_from_excel=True,source_row=2)
        twin=copy.deepcopy(event);twin.update(id='duplicate',source_row=46);d={'events':[event,twin]};self.assertEqual(archive_excel_duplicates(d),1);self.assertEqual(len(d['events']),1);self.assertEqual(d['source_duplicate_archive'][0]['event'],twin);self.assertEqual(archive_excel_duplicates(d),0)
        personal=storage.new_event('شخصی','یادآور','1405/08/30');d={'events':[personal,dict(personal,id='second')]};self.assertEqual(archive_excel_duplicates(d),0)
    def test_next_year_workbook_is_not_dropped_as_old_row(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'test.xlsx';book=Workbook();sheet=book.active;sheet.title='مانا';sheet.append(['ماه','عنوان','سررسید','یادداشت']);sheet.append(['آبان ۱۴۰۵','مالیات','پایان آذر ۱۴۰۵','']);book.save(file)
            d={'events':[],'companies':[]};self.assertEqual(storage.import_excel(file,d),(1,0));sheet['A2']='آبان ۱۴۰۶';sheet['B2']='مالیات سال بعد';sheet['C2']='پایان آذر ۱۴۰۶';book.save(file);book.close();self.assertEqual(storage.import_excel(file,d),(1,0));self.assertEqual(len(d['events']),2)
    def test_twenty_year_recurrence_dates_and_leap_clamping(self):
        for recurrence,step in [('ماهانه',1),('سه‌ماهه',3),('سالانه',12)]:
            ev=storage.new_event('شخصی','تکرار','1405/01/31',repeat=recurrence)
            for n in range(240//step):
                year,month=storage.next_month(1405,1,n*step);expected=jdatetime.date(year,month,min(31,storage.month_last_day(year,month))).togregorian();self.assertEqual(storage.occurrence(ev,expected),expected)
        self.assertEqual(storage.month_last_day(1403,12),30);self.assertEqual(storage.month_last_day(1404,12),29)

class QaUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':self.temp.name});self.env.start();d=storage.load_data();d['settings'].update(news_enabled=False,reminder_enabled=False);storage.save_data(d)
        from app import TaxWindow
        self.win=TaxWindow();self.win.timer.stop();self.win.news_panel.timer.stop()
    def tearDown(self):
        if self.win.tray:self.win.tray.hide()
        self.win.hide();self.win.deleteLater();self.app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.env.stop();self.temp.cleanup()
    def test_recurring_task_in_selected_future_month(self):
        ev=storage.new_event('مانا','کار تکراری','1405/07/30',repeat='ماهانه');self.win.events=[ev];self.win.year=1406;self.win.month=2;self.win.selected=jdatetime.date(1406,2,30);self.win.mode_filter.setCurrentText('کارهای ماه انتخابی');self.assertEqual(self.win.get_visible_events(),[ev]);self.win.refresh();row=self.win.list_layout.itemAt(0).widget();self.assertEqual(row.reference_date,jdatetime.date(1406,2,30).togregorian())
    def test_mark_done_targets_displayed_occurrence(self):
        ev=storage.new_event('مانا','تکرار','1405/07/30',repeat='ماهانه');self.win.events=[ev];future=jdatetime.date(1406,2,30).togregorian();self.win.set_done(ev,True,when=future);self.assertIn(future.isoformat(),ev['completed_occurrences']);self.assertNotIn(date.today().isoformat(),ev['completed_occurrences']);self.win.set_done(ev,False,when=future);self.assertNotIn(future.isoformat(),ev['completed_occurrences'])
    def test_custom_company_has_own_month_tab(self):
        name='شرکت آزمایشی';self.win.data['companies'].append(name);self.win.events=[storage.new_event(name,'آزمایش',storage.jformat(storage.today_j()))];self.win.refresh();overview=self.win.overview;self.assertIn(name,[overview.sections.tabText(i) for i in range(overview.sections.count())]);self.assertEqual(overview.views[name].count(),1)
    def test_all_events_pagination_reaches_last_event(self):
        self.win.mode_filter.setCurrentText('همه رویدادها');events=self.win.get_visible_events();self.win.render_items();seen=set()
        for _ in range((len(events)+self.win.items_per_page-1)//self.win.items_per_page):
            for i in range(self.win.list_layout.count()):
                row=self.win.list_layout.itemAt(i).widget()
                if hasattr(row,'item'):seen.add(row.item['id'])
            if not self.win.next_items.isEnabled():break
            self.win.change_items_page(1);self.app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(seen,{e['id'] for e in events})
    def test_save_cancel_delete_stay_outside_scroll(self):
        from app import EventDialog
        dialog=EventDialog(self.win,self.win.data['companies'],self.win.events[0]);dialog.resize(600,520);dialog.show();self.app.processEvents();buttons=dialog.findChild(QDialogButtonBox);self.assertIs(buttons.parent(),dialog);self.assertLess(buttons.geometry().bottom(),dialog.height());self.assertTrue(buttons.button(QDialogButtonBox.Save).isVisible());dialog.reject()
    def test_ics_notes_newlines_are_preserved(self):
        ev=storage.new_event('مانا','عنوان','1405/08/30',notes='خط اول\nخط دوم');self.win.events=[ev];file=Path(self.temp.name)/'out.ics'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(file),'')),patch.object(QMessageBox,'information'):
            self.win.export_ics()
        unfolded=file.read_bytes().replace(b'\r\n ',b'').decode('utf-8');self.assertIn('DESCRIPTION:خط اول\\nخط دوم\\nمانا',unfolded);self.assertNotIn('\\\\n',unfolded)
    def test_create_edit_cancel_and_delete_workflow(self):
        from app import EventDialog
        count=len(self.win.events)
        def add(dialog):
            dialog.company.setCurrentText('شرکت تازه');dialog.title.setText('آزمون افزودن');dialog.when.setText(storage.jformat(storage.today_j()));dialog.validate();return QDialog.Accepted
        with patch.object(EventDialog,'exec',add):self.win.add_event()
        self.assertEqual(len(self.win.events),count+1);ev=self.win.events[-1];self.assertEqual(ev['company'],'شرکت تازه')
        def edit(dialog):dialog.title.setText('عنوان ویرایش شده');dialog.validate();return QDialog.Accepted
        with patch.object(EventDialog,'exec',edit):self.win.edit_event(ev)
        self.assertEqual(ev['title'],'عنوان ویرایش شده')
        with patch.object(EventDialog,'exec',return_value=QDialog.Rejected):self.win.edit_event(ev)
        self.assertEqual(ev['title'],'عنوان ویرایش شده')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):self.win.delete_event(ev)
        self.assertIn(ev,self.win.events)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.win.delete_event(ev)
        self.assertNotIn(ev,self.win.events);self.assertEqual(len(storage.load_data()['events']),count)
    def test_unseen_queued_reminders_are_not_recorded_as_delivered(self):
        self.win.data['settings']['reminder_enabled']=True
        self.win.events=[storage.new_event('شخصی',str(i),storage.jformat(storage.today_j())) for i in range(10)]
        with patch.object(self.win,'_show_next_popup'):
            self.win.check_alerts();self.assertEqual(len(self.win._popup_queue),3);self.assertFalse(any(ev['last_alerts'] for ev in self.win.events));self.win.check_alerts();self.assertEqual(len(self.win._popup_queue),3)
        with patch('app.StartupPopup') as popup,patch.object(QTimer,'singleShot'):
            self.win._show_next_popup();self.assertEqual(sum(bool(e['last_alerts']) for e in self.win.events),4);popup.return_value.show_popup.assert_called_once()
            self.win.data['settings']['reminder_enabled']=False;self.win._popups.clear();self.win._show_next_popup();self.assertEqual(sum(bool(e['last_alerts']) for e in self.win.events),4)
        self.win._popup_queue.clear();self.win._popups.clear()
    def test_editing_notes_keeps_shown_alert_history(self):
        from app import EventDialog
        ev=storage.new_event('شخصی','یادآور',storage.jformat(storage.today_j()));ev['last_alerts']={'already-shown':True};self.win.events=[ev]
        def edit(dialog):dialog.notes.setPlainText('فقط یادداشت عوض شد');dialog.validate();return QDialog.Accepted
        with patch.object(EventDialog,'exec',edit):self.win.edit_event(ev)
        self.assertEqual(ev['last_alerts'],{'already-shown':True})
    def test_preferences_and_sources_save_and_reload(self):
        from settings_ui import SettingsDialog
        from appearance import apply_appearance
        def choose(dialog):
            dialog.theme.setCurrentIndex(1);dialog.default_days.setText('۱۵، ۵، ۰');dialog.colors['event_tax_color']='#117755';dialog.sources.item(0,0).setText('نام ویرایش‌شده');dialog.validate();return QDialog.Accepted
        with patch.object(SettingsDialog,'exec',choose),patch.object(self.win,'_startup_value') as startup:self.win.settings()
        self.assertEqual(storage.load_data()['settings']['theme'],'dark');self.assertEqual(self.win.data['settings']['default_lead_days'],[15,5,0]);self.assertEqual(self.win.news_panel.sources[0]['name'],'نام ویرایش‌شده');startup.assert_called_once_with(False);apply_appearance(storage.DEFAULT_SETTINGS)
    def test_news_filters_reading_and_offline_expiry(self):
        panel=self.win.news_panel;stamp=datetime.now(timezone.utc);panel.state['items']=[dict(id=str(i),title='تمدید مهلت مالیات' if i==0 else 'جریمه بیمه',source_id='tax' if i==0 else 'insurance',source='test',url='https://tax.gov.ir/',published_at=(stamp-timedelta(days=20 if i==2 else 1)).isoformat(),read=i==1,official=True) for i in range(3)]
        panel.render();self.assertEqual(len(panel.state['items']),2);panel.unread.setChecked(True);self.assertEqual(panel.items_layout.count(),1);panel.unread.setChecked(False);panel.source_filter.setCurrentIndex(panel.source_filter.findData('insurance'));self.assertEqual(panel.items_layout.count(),1)
        panel.query.setText('یافت نمی‌شود');self.assertEqual(panel.items_layout.count(),1);self.assertIn('خبری',panel.items_layout.itemAt(0).widget().text());panel.query.clear();panel.source_filter.setCurrentIndex(0);panel.read_all();self.assertTrue(all(x['read'] for x in panel.state['items']));self.assertEqual(self.win.news_button.accessibleName(),'خبرها')
        panel.state['items'].append(dict(panel.state['items'][0],id='expired',published_at=(stamp-timedelta(days=15)).isoformat()));panel.enabled.setChecked(False);panel.auto_refresh();self.assertEqual(len(panel.state['items']),2)
    def test_all_calculator_types_units_and_saved_rates(self):
        calc=self.win.calculator
        for index in range(calc.kind.count()):
            calc.kind.setCurrentIndex(index);calc.amount.setText('۱۰۰٬۰۰۰');calc.fixed.setText('۱۰');calc.monthly.setText('۲٫۵');calc.months.setText('۰٫۵');self.assertIn('۱۱,۲۵۰',calc.result.text())
            calc.unit.setCurrentText('تومان');self.assertIn('۱۱۲,۵۰۰',calc.result.toolTip());calc.unit.setCurrentText('ریال')
        calc.save_rule();self.assertEqual(storage.load_data()['penalty_rules']['custom']['monthly'],'2.5');calc.fixed.setText('۱۰۱');self.assertIn('درصد',calc.result.text());calc.amount.setText('NaN');self.assertIn('محدوده',calc.result.text())
    def test_service_link_launch_and_copy_fallback(self):
        from features_ui import open_official,SERVICES
        with patch('os.startfile') as launch:
            for _,_,url in SERVICES:self.assertTrue(open_official(url))
            self.assertEqual(launch.call_count,len(SERVICES))
        with patch('os.startfile',side_effect=OSError()),patch.object(QMessageBox,'information'):
            self.assertFalse(open_official('https://my.tax.gov.ir/'));self.assertEqual(self.app.clipboard().text(),'https://my.tax.gov.ir/')
    def test_service_buttons_keep_full_height_with_large_font(self):
        from appearance import apply_appearance
        self.win.data['settings'].update(theme='dark',font_size=19);apply_appearance(self.win.data['settings']);self.win.resize(1024,700);self.win.tabs.setCurrentWidget(self.win.services);self.win.show();self.app.processEvents()
        self.assertTrue(self.win.services.findChildren(QScrollArea))
        for button in self.win.services.findChildren(QPushButton):self.assertGreaterEqual(button.height(),button.sizeHint().height())
        apply_appearance(storage.DEFAULT_SETTINGS)

if __name__=='__main__':unittest.main(verbosity=2)

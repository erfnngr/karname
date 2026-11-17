import os,sys,tempfile,time,unittest,base64
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QScrollArea,QPushButton,QMessageBox,QDialog
from PySide6.QtCore import QBuffer,QIODevice,Qt
from PySide6.QtGui import QImage,QColor
import storage
from app import TaxWindow,ClickDay
from org_store import Store
from org_client import Client
from org_http import RunningServer

class V6UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.patch=patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':str(self.root)});self.patch.start();storage.set_profile(None);data=storage.load_data();data['events']=[storage.new_event('شخصی','نمونه',storage.jformat(storage.today_j()))];data['settings'].update(news_enabled=False,reminder_enabled=False);storage.save_data(data);self.store=Store(self.root/'company-server');self.admin=self.store.bootstrap('admin','1','مدیر نمونه');self.store.save_user(self.admin,dict(username='staff',password='ک',fullname='کارمند نمونه',memberships=[dict(company_id='mana',role='employee')]));self.server=RunningServer(self.root/'company-server','127.0.0.1',0);self.client=Client('http://127.0.0.1:'+str(self.server.port));self.user=self.client.login('admin','1');self.win=TaxWindow(dict(user=self.user,client=self.client,local_server=self.server),self.root);self.win.v8.timer.stop();self.win.v8.stop.set();self.win.workspace.timer.stop();self.win.resize(1024,700);self.win.show();self.pump(lambda:not self.win.org.busy);self.win.timer.stop();self.win.news_panel.timer.stop();self.win.org.timer.stop();self.win.desk.timer.stop();self.win.chat.timer.stop()
    def tearDown(self):
        self.win._exit_approved=True;self.win.v8.timer.stop();self.win.v8.stop.set();self.win.workspace.timer.stop();self.win.chat.timer.stop();self.win.org.timer.stop();self.win.desk.timer.stop();self.win.news_panel.timer.stop();self.win.timer.stop();self.win.tray.hide() if self.win.tray else None;self.win.company_server=None;self.win.close();self.win.deleteLater();self.app.processEvents();self.server.close();storage.set_profile(None);self.patch.stop();self.temp.cleanup()
    def pump(self,condition=None):
        end=time.time()+5
        while time.time()<end:
            self.app.processEvents();time.sleep(.01)
            if condition is None or condition():return
        raise AssertionError('UI operation timed out')
    def test_laptop_calendar_calculators_no_page_scroll(self):
        self.win.tabs.setCurrentWidget(self.win.calendar_page);self.app.processEvents();self.assertFalse(self.win.calendar_page.findChildren(QScrollArea));self.assertFalse(self.win.calculator.findChildren(QScrollArea));self.assertFalse(self.win.payroll.findChildren(QScrollArea));self.assertEqual(len(self.win.calendar_page.findChildren(ClickDay)),storage.month_last_day(self.win.year,self.win.month));self.assertTrue(all(day.height()>=48 for day in self.win.calendar_page.findChildren(ClickDay)));self.assertFalse(self.win.footer.isVisible());self.assertEqual(self.win.calendar_button.accessibleName(),'تقویم')
    def test_personal_settings_company_and_help_are_accessible(self):
        from settings_ui import SettingsDialog
        from main_ui import apply_preferences
        d=SettingsDialog(self.win);d.personal.calendar_name.setText('تقویم من');d.personal.help.setPlainText('راهنمای تیم من');d.personal.modules['news'].setChecked(False);d.personal.checks['calendar_side'].setChecked(False);d.news_terms.setText('#مالیات');d.validate();self.assertEqual(d.result(),QDialog.Accepted);apply_preferences(self.win);self.assertEqual(self.win.calendar_button.accessibleName(),'تقویم من');self.assertTrue(self.win.nav_buttons['news'].isHidden());self.assertTrue(self.win.calendar_side.isHidden());self.assertEqual(self.store.own_profile(self.admin)['preferences']['help_text'],'راهنمای تیم من');self.assertEqual(self.store.own_profile(self.admin)['preferences']['news_terms'],'#مالیات');d.deleteLater()
    def test_native_chat_sends_then_receipts_and_mute(self):
        scope='__shared_chat__';staff=Client(self.client.url);staff.login('staff','ک');room=self.store.workspace_group_create(self.admin,scope,'گروه آزمون',[staff.user['id']])['room'];chat=self.win.chat;chat.rooms=self.store.chat_rooms(self.admin);chat.selected=next(r for r in chat.rooms if r['company']==scope and r['room']==room);chat.compose.setPlainText('پیام آزمایشی 😀');chat.send();self.pump(lambda:not chat.busy);self.assertTrue(any(m['text']=='پیام آزمایشی 😀' for m in self.store.chat_list(self.admin,scope,room)['items']));self.store.chat_send(staff.user,scope,room,'پاسخ')
        self.win.data['chat_cursor']=0
        with patch.object(self.win,'popup') as popup:
            chat.poll();self.pump(lambda:not chat.busy);self.assertEqual(popup.call_count,1)
            self.store.chat_state(self.admin,scope,room,muted=True);self.store.chat_send(staff.user,scope,room,'بی‌صدا');chat.poll();self.pump(lambda:not chat.busy);self.assertEqual(popup.call_count,1)
        self.win.showMinimized();self.assertFalse(chat.reading())
    def test_photo_and_company_logo_roundtrip(self):
        image=QImage(40,40,QImage.Format_RGB32);image.fill(QColor('#167B86'));buf=QBuffer();buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');encoded=base64.b64encode(bytes(buf.data())).decode();profile=self.client.request('profile',dict(avatar=encoded,color='#070707'));self.assertTrue(profile['avatar']);co=self.client.request('companies',dict(name='نمونه تازه',logo=encoded,color='#187C85',phone='021',address='نشانی نمونه'));self.assertTrue(co['logo']);self.assertEqual(co['phone'],'021')
        from brand import register_company,company_pixmap,popup_style
        register_company(co);self.assertFalse(company_pixmap(co['name']).isNull());self.assertEqual(popup_style(co['name'],storage.DEFAULT_SETTINGS)[0]['popup_bg'],'#187C85')
    def test_exit_without_backup_is_explicit(self):
        self.pump(lambda:not any((self.win.org.busy,self.win.chat.busy,self.win.desk.busy,self.win.attendance.busy,self.win.ai.applying,self.win.workspace.busy,getattr(self.win.v8,'backup_busy',False))))
        with patch.object(QMessageBox,'information') as info,patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.win,'exit_app') as exit_app,patch.object(self.win,'backup_now') as backup:
            self.win.exit_without_backup();info.assert_not_called();self.assertTrue(self.win._exit_approved);exit_app.assert_called_once();backup.assert_not_called()
    def test_personal_recovery_restores_preferences_after_next_login(self):
        import copy,json
        from backup_bundle import create_bundle,verify_bundle
        from PySide6.QtWidgets import QFileDialog
        data=copy.deepcopy(self.win.data);data['preferences']={'calendar_name':'بازیابی‌شده'};profile={'avatar':'','color':'#ABCDEF','preferences':data['preferences']};path=self.root/'restore.karname';create_bundle(path,data,{'account/profile.json':json.dumps({'id':self.admin['id'],'profile':profile}).encode()});self.store.save_profile(self.admin,{'color':'#000000','preferences':{'calendar_name':'جدیدتر'}})
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(QApplication,'quit') as quit_app:self.win.restore_backup();quit_app.assert_called_once()
        self.assertEqual(storage.load_data()['preferences']['calendar_name'],'بازیابی‌شده');self.assertTrue(list((self.root/'backups').glob('before-restore-*.karname')))
        # QApplication.quit is mocked; simulate the next login on this fixture.
        self.win._exit_approved=False
        self.server=RunningServer(self.root/'company-server','127.0.0.1',0);self.client=Client('http://127.0.0.1:'+str(self.server.port));self.client.login('admin','1');self.win.org.client=self.client;self.win.company_server=self.server;self.win.org.sync();self.pump(lambda:not self.win.org.busy);self.assertEqual(self.server.store.own_profile(self.admin)['color'],'#ABCDEF');self.assertNotIn('pending_profile_restore',self.win.data)
    def test_news_hashtag_and_link_filter_and_no_count(self):
        from datetime import datetime,timezone
        panel=self.win.news_panel;panel.state['items']=[dict(id='a',source_id='tax',source='مالیات',title='تمدید مالیات',url='https://www.intamedia.ir/tax-news',published_at=datetime.now(timezone.utc).isoformat(),read=False),dict(id='b',source_id='tax',source='مالیات',title='خبر بیمه',url='https://www.intamedia.ir/insurance',published_at=datetime.now(timezone.utc).isoformat(),read=False)];self.win.data['preferences']={'news_terms':'#مالیات'};panel.render();self.assertEqual(panel.items_layout.count(),1);self.win.data['preferences']['news_terms']='';panel.query.setText('insurance');panel.render();self.assertEqual(panel.items_layout.count(),1);self.assertEqual(self.win.news_button.accessibleName(),'خبرها');self.assertEqual(panel.check.text(),'بروزرسانی');self.assertFalse(any(b.text() in ('باز کردن منبع','پیشنهاد تغییر موعد شرکت') for b in panel.findChildren(QPushButton)))

if __name__=='__main__':unittest.main(verbosity=2)

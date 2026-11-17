import os,sys,time,copy,json,threading,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
import test_v6_ui as fixtures

class V8UiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):fixtures.V6UiTests.setUp(self)
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_forward_distinguishes_groups_with_identical_titles(self):
        from chat_ui import room_labels
        from PySide6.QtWidgets import QInputDialog
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);first=self.store.workspace_group_create(self.admin,scope,'همکاران',[staff['id']]);second=self.store.workspace_group_create(self.admin,scope,'همکاران',[staff['id']]);self.store.chat_send(self.admin,scope,first['room'],'پیام نمونه')
        chat=self.win.chat;self.pump(lambda:not chat.busy);chat.rooms=self.store.chat_rooms(self.admin);labels=room_labels(chat.rooms);self.assertEqual(len(labels),len(set(labels)));destination=labels[next(i for i,r in enumerate(chat.rooms) if r['room']==second['room'])];message=self.store.chat_list(self.admin,scope,first['room'])['items'][0]
        with patch.object(QInputDialog,'getItem',return_value=(destination,True)):chat.forward_message(message);self.pump(lambda:not chat.busy)
        self.assertEqual(self.store.chat_list(self.admin,scope,second['room'])['items'][0]['text'],'پیام نمونه');self.assertEqual(len(self.store.chat_list(self.admin,scope,first['room'])['items']),1)
    def test_forward_message_and_file_to_personal_conversation(self):
        import base64
        from PySide6.QtWidgets import QInputDialog
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);group=self.store.workspace_group_create(self.admin,scope,'گروه آزمون',[staff['id']])['room'];direct=self.store.workspace_direct(self.admin,scope,staff['id']);chat=self.win.chat;self.pump(lambda:not chat.busy);chat.rooms=self.store.chat_rooms(self.admin);source=self.store.chat_send(self.admin,scope,group,text='پیام نمونه',attachments=[{'name':'a.txt','data':base64.b64encode(b'data').decode()}]);message=next(m for m in self.store.chat_list(self.admin,scope,group)['items'] if m['id']==source['id']);destination=direct['display_title']
        with patch.object(QInputDialog,'getItem',return_value=(destination,True)):chat.forward_message(message);self.pump(lambda:not chat.busy)
        found=self.store.chat_list(self.admin,scope,direct['room'])['items'];self.assertEqual(found[-1]['text'],'پیام نمونه');self.assertEqual(found[-1]['files'][0]['name'],'a.txt')
    def test_trash_button_selection_color_and_restore(self):
        from PySide6.QtCore import Qt
        note=self.store.desk_note_save(self.admin,dict(title='یادداشت حذف‌شده',body='متن'));self.store.desk_note_delete(self.admin,note['id'],1);w=self.win.workspace;self.pump(lambda:not w.busy);self.win.trash_button.click();self.pump(lambda:not w.busy and any(r['id']==note['id'] for r in w.trash));self.assertTrue(w.recycle.isVisible());self.assertEqual(w.pages.indexOf(w.recycle),-1)
        index=next(i for i,r in enumerate(w.trash) if r['id']==note['id']);w.trash_table.item(index,0).setCheckState(Qt.Checked);self.assertEqual(w.trash_table.item(index,1).background().color().name(),'#dff2e5');w.trash_mode.setCurrentIndex(w.trash_mode.findData('purge'));self.assertEqual(w.trash_table.item(index,1).background().color().name(),'#fbe3e7');w.trash_mode.setCurrentIndex(w.trash_mode.findData('restore'));w.apply_trash();self.pump(lambda:not w.busy);self.assertTrue(any(n['id']==note['id'] for n in self.store.desk_snapshot(self.admin)['notes']))
    def test_sidebar_palette_and_restricted_shortcut(self):
        from workspace_ui import CommandPalette
        from main_ui import apply_preferences
        self.win.sidebar.flip();self.assertEqual(self.win.nav_buttons['news'].accessibleName(),'خبرها');self.assertEqual(self.win.calendar_button.accessibleName(),'تقویم');d=CommandPalette(self.win);self.assertTrue(any('تردد' in d.list.item(i).text() for i in range(d.list.count())));d.deleteLater()
        staff=self.store.user(self.store.login('staff','ک')['user']['id']);staff['memberships'][0]['permissions']={'module.calendar.view':False,'module.settings.view':False};self.win.session_user=staff;apply_preferences(self.win);self.assertFalse(self.win.calendar_action.isVisible());self.assertTrue(self.win.occasions_action.isVisible());self.assertTrue(self.win.settings_button.isHidden());d=CommandPalette(self.win);self.assertFalse(any('افزودن یادآور' in d.list.item(i).text() for i in range(d.list.count())));d.deleteLater()
        with patch('app.QMessageBox.information') as info:
            count=len(self.win.events);self.win.add_event();self.assertEqual(len(self.win.events),count);info.assert_called_once()
    def test_task_pages_reach_last_item_and_board_is_lazy(self):
        w=self.win.workspace;tasks=[]
        for i in range(123):tasks.append(dict(id='task-'+str(i),title='نمونه '+str(i),kind='task',payload=dict(title='نمونه '+str(i),due_date='1405/08/10',status='draft'),company_id='mana',owner_id=self.admin['id'],private=False,version=1,department='',mine=True,review=False,overdue=False,due_today=False,saved=False))
        w.snapshot=dict(tasks=tasks,requests=[],views=[],notifications=[]);w.companies=[dict(id='mana',name='مانا')];w.view.clear();w.view.addItem('همه کارها',{});w.render();self.assertEqual(w.today_table.rowCount(),50);self.assertFalse(w.columns['draft'].count());w.change_page(1);self.assertEqual(w.page_tasks[0]['id'],'task-50');w.change_page(1);self.assertEqual(w.today_table.rowCount(),23);self.assertEqual(w.page_tasks[-1]['id'],'task-122');w.pages.setCurrentIndex(1);self.assertEqual(w.columns['draft'].count(),123)
    def test_monthly_attendance_report_is_connected_to_real_api(self):
        staff=self.store.user(self.store.login('staff','ک')['user']['id']);self.store.save_record(self.admin,'employee',dict(title='کارمند نمونه',employee_code='001',user_id=staff['id']),'mana');self.store.import_attendance(self.admin,'mana',[dict(employee_code='001',date='1405/08/02',check_in='09:00',check_out='18:00',minutes='540')],'1405/08')
        panel=self.win.attendance;panel.year.setValue(1405);panel.month.setCurrentIndex(7);panel.reload();self.pump(lambda:not panel.busy and panel.company.count()>0);panel.company.setCurrentIndex(panel.company.findData('mana'));self.pump(lambda:not panel.busy and panel.report is not None);self.assertEqual(panel.report['totals']['worked_minutes'],540);self.assertEqual(panel.person.count(),1);self.assertEqual(panel.table.item(0,0).text(),'۱۴۰۵/۰۸/۰۱')
    def test_native_personal_chat_queue_and_reply_roundtrip(self):
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);entry=self.store.workspace_direct(self.admin,scope,staff['id']);chat=self.win.chat;chat.selected=entry;chat.rooms=[entry];chat.compose.setPlainText('پیام خصوصی آزمایشی');chat.send();self.pump(lambda:not chat.busy and chat.delivery is not None and not chat.delivery.value['outbox']);messages=self.store.chat_list(self.admin,scope,entry['room'])['items'];self.assertEqual(len(messages),1);chat.reply_to=messages[0]['id'];chat.compose.setPlainText('پاسخ خصوصی');chat.send();self.pump(lambda:not chat.busy and not chat.delivery.value['outbox']);self.assertEqual(len(self.store.chat_list(self.admin,scope,entry['room'],thread=messages[0]['id'])['items']),2)
    def test_send_during_background_fetch_flushes_immediately_after_fetch(self):
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);room=self.store.workspace_group_create(self.admin,scope,'گروه آزمون',[staff['id']])['room'];chat=self.win.chat;self.pump(lambda:not chat.busy);chat.rooms=self.store.chat_rooms(self.admin);chat.selected=next(r for r in chat.rooms if r['company']==scope and r['room']==room);release=threading.Event();chat.run(lambda c:release.wait(2),lambda _:None);chat.compose.setPlainText('ارسال هنگام بارگذاری');chat.send();self.assertTrue(chat.delivery.pending());release.set();self.pump(lambda:not chat.busy and not chat.delivery.value['outbox']);self.assertEqual(sum(m['text']=='ارسال هنگام بارگذاری' for m in self.store.chat_list(self.admin,scope,room)['items']),1)

class HostLifecycleTests(unittest.TestCase):
    def test_independent_host_launch_is_explicit_and_stop_waits(self):
        from network_tools import start_autohost,stop_autohost
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch('network_tools.subprocess.Popen') as launch:
                self.assertIsNone(start_autohost(root));launch.assert_not_called();(root/'company-host-autostart.json').write_text('{"enabled":true}');start_autohost(root);self.assertIn('--company-host',launch.call_args.args[0]);self.assertEqual(launch.call_args.args[0][-1],str(root.resolve()))
            (root/'company-host-status.json').write_text(json.dumps(dict(running=True,pid=os.getpid())))
            def finish():
                while not (root/'company-host.stop').exists():time.sleep(.01)
                (root/'company-host-status.json').write_text('{"running":false}')
            worker=threading.Thread(target=finish);worker.start();stop_autohost(root,2);worker.join(2);self.assertFalse(worker.is_alive())

if __name__=='__main__':unittest.main()

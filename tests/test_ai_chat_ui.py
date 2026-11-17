import os,sys,json,time,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt
import test_v6_ui as fixtures
import test_lmstudio as endpoints
from ai_chat_ui import LMStudioSettings,PlanPreview
from main_ui import apply_preferences

class AIUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.model_patch=patch('ai_chat_ui.GEMMA_MODEL','local-chat');self.model_patch.start();fixtures.V6UiTests.setUp(self);self.fixture=endpoints.LMClientTests();self.fixture.setUp();self.secret_patch=patch('ai_chat_ui.token',return_value='');self.secret_patch.start();self.win.data['settings']['lmstudio']={'url':self.fixture.client.url,'model':''}
    def tearDown(self):self.win.ai.cancel();self.secret_patch.stop();self.fixture.tearDown();fixtures.V6UiTests.tearDown(self);self.model_patch.stop()
    pump=fixtures.V6UiTests.pump
    def test_web_bridge_uses_existing_assistant_and_real_response_path(self):
        from react_assistant_bridge import ReactAssistantBridge
        ai=self.win.ai;ai.mode.setCurrentIndex(ai.mode.findData('chat'));ai.apply_access();bridge=ReactAssistantBridge(ai);results=[];states=[]
        bridge.completed.connect(lambda key,raw:results.append(json.loads(raw)));bridge.changed.connect(lambda raw:states.append(json.loads(raw)))
        bridge.request('suggest-short','suggest',json.dumps({'text':'فاکتور'}));self.assertEqual(results[-1]['value'],[])
        bridge.request('suggest-long','suggest',json.dumps({'text':'فاکتور جدید'}));self.assertTrue(results[-1]['value'])
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw):
            bridge.request('send','send',json.dumps({'text':'سلام از نمای جدید'}));self.assertTrue(results[-1]['ok'],results);self.pump(lambda:not ai.busy);bridge.publish()
        self.assertTrue(any(item['content']=='سلام از نمای جدید' for item in states[-1]['items']))
        self.assertTrue(any('سلام از مدل محلی' in item['content'] for item in states[-1]['items']))
        self.assertTrue(endpoints.FakeLM.requests);bridge.close()
    def test_saved_conversation_restores_without_replaying_actions(self):
        from ai_memory import save_conversation
        ai=self.win.ai;self.assertNotEqual(ai.user_id(),'standalone')
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw):
            turns=[{'role':'user','content':'یک جلسه بساز'},{'role':'assistant','content':'چه تاریخی؟'}]
            save_conversation(ai.user_id(),turns,ai.scope_stamp)
            with patch.object(ai,'apply_app_actions') as apply:
                ai.restore_conversation();self.assertEqual(ai.history,turns);apply.assert_not_called()
            ai.new_conversation();self.assertEqual(ai.history,[])
            ai.restore_conversation();self.assertEqual(ai.history,[])
    def test_why_reports_actual_error_without_calling_model(self):
        ai=self.win.ai;ai.history=[{'role':'user','content':'برای شنبه جلسه بساز'},{'role':'assistant','content':'درخواست قابل اجرا نیست: تاریخ دقیق مشخص نیست.'}];ai.prompt.setPlainText('چرا')
        with patch('ai_chat_ui.make_client') as client,patch.object(ai,'store_conversation'):
            ai.send();client.assert_not_called()
        self.assertIn('تاریخ دقیق مشخص نیست',ai.history[-1]['content']);self.assertNotIn('دسترسی ندارم',ai.history[-1]['content'])
    def test_request_journal_uses_real_execution_result(self):
        from ai_memory import read_requests,save_request
        ai=self.win.ai;ai.pending_prompt='کار نمونه بساز';ai.pending_journal_request=ai.pending_prompt;ai.pending_request_id='test-id';ai.app_context={'test':True}
        action={'type':'task_create','changes':{}};ai.app_actions=[action];ai.history=[{'role':'user','content':ai.pending_prompt},{'role':'assistant','content':'در حال انجام'}]
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw),patch('ai_chat_ui.allowed',return_value=True):
            save_request(ai.user_id(),ai.scope_stamp,'test-id',ai.pending_prompt,'processing')
            with patch('ai_app_actions.execute',return_value=[{'ok':False,'action':action,'message':'ذخیره نشد'}]):ai.apply_app_actions()
            self.assertEqual(read_requests(ai.user_id(),ai.scope_stamp)[-1]['status'],'failed')
            ai.app_actions=[action]
            with patch('ai_app_actions.execute',return_value=[{'ok':True,'action':action,'message':'ذخیره شد'}]):ai.apply_app_actions()
            self.assertEqual(read_requests(ai.user_id(),ai.scope_stamp)[-1]['status'],'completed')
            self.assertEqual(len(read_requests(ai.user_id(),ai.scope_stamp)),1)
    def test_leave_action_intents_and_payment_word(self):
        from ai_chat_ui import explicit_action_requested
        self.assertTrue(explicit_action_requested('فردا بررسی قرارداد یادم بیار'))
        self.assertTrue(explicit_action_requested('به همکار پیغام بدید سلام'))
        for prompt in ('درخواست مرخصی را لغو کن','مرخصی را تایید کن','مرخصی را رد کن'):
            self.assertTrue(explicit_action_requested(prompt))
        self.assertFalse(explicit_action_requested('گزارش پرداخت را نشان بده'))
        for prompt in ('فردا ساعت نه یادم بنداز', 'به علی پیام بده', 'به علی پیغام بده', 'این کار رو برام درست کن'):
            self.assertTrue(explicit_action_requested(prompt))
        self.assertFalse(explicit_action_requested('این را حذف نکن'))
        self.assertFalse(explicit_action_requested('نمی‌خوام این را حذف کن'))
        self.assertFalse(explicit_action_requested('چطور برای فردا برنامه بچینم؟'));self.assertFalse(explicit_action_requested('برنامه بچین اما الان نچین'))
    def test_natural_message_reaches_the_executor(self):
        ai=self.win.ai;ai.pending_prompt='به علی پیام بده سلام';ai.app_context={'test':True};action={'type':'message_send','changes':{'text':'سلام'}};ai.app_actions=[action]
        with patch('ai_chat_ui.allowed',return_value=True),patch('ai_app_actions.execute',return_value=[{'ok':True,'action':action,'message':'انجام شد'}]) as execute,patch.object(ai,'save_memory'):
            ai.apply_app_actions();execute.assert_called_once()
    def test_personal_memory_is_recalled_and_suggestions_follow_typing(self):
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw):
            from ai_memory import read
            ai=self.win.ai;ai.mode.setCurrentIndex(ai.mode.findData('chat'));ai.prompt.setPlainText('فاکتور');self.app.processEvents();self.assertFalse(any(not b.isHidden() for b in ai.suggest_buttons));ai.prompt.setPlainText('فاکتور جدید');self.app.processEvents();self.assertTrue(any(not b.isHidden() for b in ai.suggest_buttons));self.assertTrue(ai.more_templates.isHidden())
            ai.prompt.setPlainText('بیمه شرکت را بررسی کن');ai.send();self.pump(lambda:not ai.busy);self.assertEqual(len(read(ai.user_id())),1)
            ai.reset();ai.mode.setCurrentIndex(ai.mode.findData('chat'));ai.prompt.setPlainText('بیمه چه شد؟');ai.send();self.pump(lambda:not ai.busy)
            self.assertIn('بیمه شرکت را بررسی کن',endpoints.FakeLM.requests[-1]['messages'][0]['content']);self.assertEqual(len(read(ai.user_id())),2)
    def test_connection_form_shows_only_relevant_fields(self):
        panel=LMStudioSettings(self.win);panel.show();self.app.processEvents();panel.cloud_enabled.setChecked(False);self.assertTrue(panel.cloud_model.isHidden());self.assertTrue(panel.url.isHidden());panel.cloud_enabled.setChecked(True);self.assertFalse(panel.cloud_model.isHidden());self.assertFalse(panel.cloud_key.isHidden());self.assertTrue(panel.cloud_url.isHidden());panel.advanced.setChecked(True);self.assertFalse(panel.cloud_url.isHidden());panel.cloud_enabled.setChecked(False);self.assertFalse(panel.url.isHidden());panel.deleteLater()
    def test_service_indicator_distinguishes_saved_and_unsaved_selection(self):
        with patch('avalai_client.load_credentials',return_value={}):
            panel=LMStudioSettings(self.win);self.assertIn('سرویس ذخیره‌شده: Gemma',panel.provider_indicator.text());self.assertNotIn('انتخاب جدید',panel.provider_indicator.text());panel.cloud_enabled.setChecked(True);panel.cloud_model.setText('my-model');self.assertIn('سرویس ذخیره‌شده: Gemma',panel.provider_indicator.text());self.assertIn('انتخاب جدید پس از ذخیره: اول‌ای‌آی با کلید شخصی · my-model',panel.provider_indicator.text());panel.cloud_enabled.setChecked(False);self.assertNotIn('انتخاب جدید',panel.provider_indicator.text());panel.deleteLater()
        with patch('avalai_client.load_credentials',return_value={'active':True,'model':'cloud-model','url':'https://api.avalai.ir/v1','key':'secret'}):
            panel=LMStudioSettings(self.win);self.assertIn('سرویس ذخیره‌شده: اول‌ای‌آی با کلید شخصی · cloud-model',panel.provider_indicator.text());self.assertNotIn('secret',panel.provider_indicator.text());panel.cloud_enabled.setChecked(False);self.assertIn('انتخاب جدید پس از ذخیره: Gemma',panel.provider_indicator.text());panel.deleteLater()
    def test_chat_schedule_button_stores_message_without_sending(self):
        from datetime import datetime,timezone,timedelta
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);room=self.store.workspace_group_create(self.admin,scope,'گروه آزمون',[staff['id']])['room']
        chat=self.win.chat;self.pump(lambda:not chat.busy);chat.selected=next(r for r in self.store.chat_rooms(self.admin) if r['company']==scope and r['room']==room);chat.compose.setPlainText('سلام زمان‌دار')
        with patch('chat_ui.ScheduleDialog') as dialog:
            dialog.return_value.exec.return_value=QDialog.Accepted;dialog.return_value.due_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();chat.schedule_message();self.pump(lambda:not chat.busy)
        rows=self.store.chat_scheduled_list(self.admin,scope,room);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['text'],'سلام زمان‌دار');self.assertFalse(self.store.chat_list(self.admin,scope,room)['items']);self.assertEqual(chat.compose.toPlainText(),'')
    def test_chat_schedule_button_accepts_attachment_only(self):
        from datetime import datetime,timezone,timedelta
        import base64
        scope='__shared_chat__';staff=self.store.user(self.store.login('staff','ک')['user']['id']);room=self.store.workspace_group_create(self.admin,scope,'گروه آزمون',[staff['id']])['room']
        chat=self.win.chat;self.pump(lambda:not chat.busy);chat.selected=next(r for r in self.store.chat_rooms(self.admin) if r['company']==scope and r['room']==room);chat.files=[dict(name='sample.txt',data=base64.b64encode(b'test').decode(),size=4)]
        with patch('chat_ui.ScheduleDialog') as dialog:
            dialog.return_value.exec.return_value=QDialog.Accepted;dialog.return_value.due_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();chat.schedule_message();self.pump(lambda:not chat.busy)
        rows=self.store.chat_scheduled_list(self.admin,scope,room);self.assertEqual(rows[0]['file_names'],['sample.txt']);self.assertFalse(chat.files);self.assertFalse(self.store.chat_list(self.admin,scope,room)['items'])
    def test_schedule_dialog_formats_date_and_time_in_readable_direction(self):
        from chat_ui import ScheduleDialog
        dialog=ScheduleDialog(self.win);self.assertEqual(dialog.day.layoutDirection(),Qt.LeftToRight);self.assertEqual(dialog.time.layoutDirection(),Qt.LeftToRight);self.assertEqual(dialog.time.displayFormat(),'HH:mm');dialog.day.setText('invalid');dialog.validate();self.assertNotEqual(dialog.result(),QDialog.Accepted);self.assertTrue(dialog.error.text());dialog.deleteLater()
    def test_scheduled_assistant_prompt_waits_for_draft_and_runs_once(self):
        from datetime import datetime,timezone,timedelta
        from ai_schedule import add,read,write
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw),patch.object(self.win,'popup') as popup:
            ai=self.win.ai;user=ai.user_id();entry=add(user,'سلام زمان‌دار','chat',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat());items=read(user);items[0]['due_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();write(user,items);ai.prompt.setPlainText('پیش‌نویس فعلی');ai.process_scheduled_prompts();self.assertEqual(read(user)[0]['status'],'pending');self.assertEqual(ai.prompt.toPlainText(),'پیش‌نویس فعلی');ai.prompt.clear();ai.process_scheduled_prompts();self.pump(lambda:not ai.busy);self.assertEqual(read(user)[0]['status'],'completed');self.assertEqual(ai.history[-1]['content'],'سلام از مدل محلی');self.assertEqual(ai.mode.currentData(),'app');self.assertEqual(len(endpoints.FakeLM.requests),1);popup.assert_called_once();ai.process_scheduled_prompts();self.assertEqual(len(endpoints.FakeLM.requests),1)
    def test_scheduled_assistant_action_completes_after_application(self):
        from datetime import datetime,timezone,timedelta
        from ai_schedule import add,read,write
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw),patch.object(self.win,'popup'):
            ai=self.win.ai;user=ai.user_id();add(user,'اعلان کارم را سه روز قبل تنظیم کن','app',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat());items=read(user);items[0]['due_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();write(user,items);endpoints.FakeLM.mode='app';ai.process_scheduled_prompts();self.pump(lambda:read(user)[0]['status']=='completed');self.assertEqual(self.win.events[0]['lead_days'],[3]);self.assertIn('نتیجه واقعی برنامه',ai.transcript.toPlainText())
    def test_backup_contains_current_users_scheduled_requests(self):
        from datetime import datetime,timezone,timedelta
        from ai_schedule import add
        from backup_bundle import verify_bundle
        from PySide6.QtWidgets import QFileDialog
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw):
            add(self.win.ai.user_id(),'درخواست پشتیبان','chat',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat());self.win.ai.schedule_changed();self.assertTrue(self.win.backup_state.dirty(self.win.data));target=self.root/'schedule-backup.karname'
            with patch.object(QFileDialog,'getSaveFileName',return_value=(str(target),'')):self.assertTrue(self.win.backup_now())
            entries=verify_bundle(target)[1];value=json.loads(entries['account/assistant-schedules.json']);self.assertEqual(value['user_id'],self.win.ai.user_id());self.assertEqual(value['items'][0]['prompt'],'درخواست پشتیبان');self.assertFalse(self.win.backup_state.dirty(self.win.data))
    def test_assistant_backup_creates_recoverable_archive_without_dialog(self):
        from ai_app_actions import capture,collect,execute
        from backup_bundle import verify_bundle
        from PySide6.QtWidgets import QFileDialog
        self.pump(lambda:not self.win.org.busy and not self.win.desk.busy)
        ctx=collect(capture(self.win),'نسخه پشتیبان تهیه کن')
        with patch.object(QFileDialog,'getSaveFileName',side_effect=AssertionError('unexpected dialog')):
            result=execute(self.win,[{'type':'backup_create'}],ctx,self.client.request)
        self.assertTrue(result[0]['ok'],result)
        self.assertTrue(Path(self.win._last_backup).is_file());verify_bundle(Path(self.win._last_backup))
    def test_automatic_backup_contains_scheduled_requests(self):
        from datetime import datetime,timezone,timedelta
        from ai_schedule import add
        from backup_bundle import verify_bundle
        with patch('local_vault.transform',side_effect=lambda raw,decrypt=False:raw),patch('v8_controller.load',return_value={'password':'backup-test'}):
            add(self.win.ai.user_id(),'درخواست زمان‌بندی','chat',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat());self.win.data['settings']['backup_folder']=str(self.root/'automatic');self.win.v8.backup(manual=True);self.pump(lambda:not self.win.v8.backup_busy);files=list((self.root/'automatic').glob('*.karname'));self.assertTrue(files);entries=verify_bundle(files[0],'backup-test')[1];self.assertEqual(json.loads(entries['account/assistant-schedules.json'])['items'][0]['prompt'],'درخواست زمان‌بندی')
    def test_real_http_stream_updates_chat_and_does_not_write_calendar(self):
        ai=self.win.ai;before=len(self.win.events);ai.prompt.setPlainText('سلام');ai.send();self.pump(lambda:not ai.busy);self.assertEqual(ai.history[-1]['content'],'سلام از مدل محلی');self.assertIn('سلام از مدل محلی',ai.transcript.toPlainText());self.assertEqual(len(self.win.events),before);self.assertEqual(ai.model.currentText(),'local-chat')
    def test_plan_saves_without_review(self):
        endpoints.FakeLM.mode='plan';ai=self.win.ai;ai.mode.setCurrentIndex(1);ai.prompt.setPlainText('یک برنامه نمونه برای 1405/08/12 بچین');before=len(self.win.events);ai.send();self.pump(lambda:not ai.busy);self.assertEqual(len(self.win.events),before+1);self.assertEqual(self.win.events[-1]['company'],'شخصی');self.assertEqual(self.win.events[-1]['lead_days'],self.win.data['settings']['personal_lead_days']);self.assertFalse(ai.plan_button.isEnabled())
    def test_plan_does_not_create_a_model_guessed_date(self):
        endpoints.FakeLM.mode='plan';ai=self.win.ai;ai.mode.setCurrentIndex(1);ai.prompt.setPlainText('یک برنامه نمونه بساز');before=len(self.win.events);ai.send();self.pump(lambda:not ai.busy)
        self.assertEqual(len(self.win.events),before);self.assertIn('تاریخ',ai.items[-1]['content']);self.assertFalse(ai.proposals);self.assertFalse(ai.plan_button.isEnabled())
    def test_plan_question_does_not_create_any_reminder(self):
        endpoints.FakeLM.mode='plan';ai=self.win.ai;ai.mode.setCurrentIndex(1);ai.prompt.setPlainText('چگونه برای 1405/08/12 برنامه تنظیم کنم؟');before=len(self.win.events);ai.send();self.pump(lambda:not ai.busy)
        self.assertEqual(len(self.win.events),before);self.assertFalse(ai.proposals)
    def test_cancelled_review_or_invalid_date_never_writes(self):
        row=dict(title='پیشنهاد',date_jalali='1405/08/12',lead_days=[1,0],recurrence='بدون تکرار',notes='');ai=self.win.ai;ai.proposals=[row];before=len(self.win.events)
        with patch.object(PlanPreview,'exec',return_value=QDialog.Rejected):ai.preview()
        self.assertEqual(len(self.win.events),before);dialog=PlanPreview(self.win,[row]);dialog.table.item(0,2).setText('invalid');dialog.validate();self.assertNotEqual(dialog.result(),QDialog.Accepted);dialog.deleteLater()
    def test_calendar_navigation_matches_buttons_in_both_sidebar_modes(self):
        for collapsed in (False,True):
            self.win.data.setdefault('preferences',{})['sidebar_collapsed']=collapsed;self.win.sidebar.apply();self.app.processEvents();a=self.win.calendar_button;b=self.win.nav_buttons['home'];self.assertEqual(a.width(),b.width());self.assertEqual(a.height(),b.height())
    def test_permissions_and_changed_identity_clear_history_and_ignore_late_chunks(self):
        ai=self.win.ai;ai.history=[dict(role='user',content='private')];ai.items=[dict(role='user',content='private')];job=ai.begin();staff=self.store.user(self.store.login('staff','ک')['user']['id']);staff['memberships'][0]['permissions']={'module.assistant.use':False,'module.assistant.configure':False};self.win.session_user=staff;apply_preferences(self.win);ai.piece(job,'late private result');self.assertFalse(ai.history);self.assertFalse(ai.items);self.assertFalse(ai.send_button.isEnabled());self.assertTrue(ai.settings_button.isHidden())
    def test_credentials_not_in_plain_settings_and_revocation_blocks_changes(self):
        panel=LMStudioSettings(self.win);panel.key.setText('sample-not-a-real-token');values=panel.values();self.assertNotIn('sample-not-a-real-token',json.dumps(values))
        with patch('local_vault.save') as save:panel.commit();self.assertEqual(save.call_args.args[1]['token'],'sample-not-a-real-token')
        self.win.session_user=self.store.user(self.store.login('staff','ک')['user']['id']);self.win.session_user['memberships'][0]['permissions']={'module.assistant.configure':False};panel.url.setText('http://192.168.1.8:1234');self.assertEqual(panel.values()['url'],self.fixture.client.url)
        with patch('local_vault.save') as save:panel.commit();save.assert_not_called()
        panel.deleteLater()
    def test_application_assistant_applies_explicit_request(self):
        endpoints.FakeLM.mode='app';ai=self.win.ai;ai.prompt.setPlainText('اعلان کارم را سه روز قبل تنظیم کن');ai.send();self.pump(lambda:self.win.events[0]['lead_days']==[3]);self.assertIn('داده فعلی برنامه:',endpoints.FakeLM.requests[0]['messages'][0]['content'])
        self.assertEqual(self.win.events[0]['lead_days'],[3]);self.assertTrue(self.win.events[0]['reminder_custom']);self.assertFalse(ai.app_actions);self.assertIn('نتیجه واقعی برنامه',ai.transcript.toPlainText());self.assertEqual([x['role'] for x in ai.history],['user','assistant']);self.assertIn('نتیجه واقعی برنامه',ai.history[-1]['content'])
    def test_structured_responses_never_show_raw_stream(self):
        ai=self.win.ai
        for mode,index,prompt in [('app',2,'اعلان کارم را سه روز قبل تنظیم کن'),('plan',1,'یک برنامه نمونه')]:
            with self.subTest(mode=mode):
                ai.reset();endpoints.FakeLM.mode=mode;ai.mode.setCurrentIndex(index);snapshots=[]
                def observe(job,piece):
                    ai.render();snapshots.append(ai.transcript.toPlainText())
                    if len(snapshots)==1:ai.mode.setCurrentIndex(0)
                ai.bridge.piece.connect(observe)
                try:
                    ai.prompt.setPlainText(prompt);ai.send();self.pump(lambda:not ai.busy and not ai.applying)
                    self.assertTrue(snapshots)
                    for snapshot in snapshots:
                        self.assertNotIn('"reply"',snapshot);self.assertNotIn('"actions"',snapshot);self.assertNotIn('"reminders"',snapshot)
                    self.assertNotIn('"actions"',ai.transcript.toPlainText())
                finally:ai.bridge.piece.disconnect(observe)
    def test_invalid_plan_does_not_display_json(self):
        ai=self.win.ai;job=ai.begin();ai.structured_job=job;ai.items=[dict(role='assistant',content='')];ai.reply_index=0;ai.pending_prompt='برنامه'
        ai.piece(job,'{"reminders":');ai.render();self.assertNotIn('reminders',ai.transcript.toPlainText())
        ai.finished(job,dict(answer='{"reminders":',history=[],planning=True,application=False),None)
        self.assertNotIn('reminders',ai.transcript.toPlainText());self.assertIn('قابل ثبت نیست',ai.transcript.toPlainText())
    def test_planning_question_is_shown_and_followup_date_is_used(self):
        from ai_chat_ui import clarification_request
        ai=self.win.ai;job=ai.begin();ai.structured_job=job;ai.items=[dict(role='assistant',content='')];ai.reply_index=0;ai.pending_prompt='برای ارسال اظهارنامه برنامه بچین';ai.pending_action_prompt=ai.pending_prompt
        ai.finished(job,dict(answer='لطفاً تاریخ را مشخص کنید.',history=[dict(role='user',content=ai.pending_prompt)],planning=True,application=False),None)
        self.assertIn('تاریخ را مشخص کنید',ai.items[0]['content']);self.assertFalse(ai.proposals)
        effective=clarification_request(ai.history,'1405/09/01');self.assertIn('اظهارنامه',effective)
        job=ai.begin();ai.structured_job=job;ai.items.append(dict(role='assistant',content=''));ai.reply_index=1;ai.pending_prompt='1405/09/01';ai.pending_action_prompt=effective
        ai.finished(job,dict(answer='{"reminders":[{"title":"ارسال اظهارنامه","date_jalali":"1405/09/01"}]}',history=ai.history+[dict(role='user',content='1405/09/01')],planning=True,application=False),None)
        self.assertTrue(any(e['title']=='ارسال اظهارنامه' and e['date_jalali']=='1405/09/01' for e in self.win.events))
    def test_planning_followup_through_model_connection_and_ui(self):
        endpoints.FakeLM.mode='plan_followup';ai=self.win.ai;ai.mode.setCurrentIndex(1);before=len(self.win.events)
        ai.prompt.setPlainText('برای پیگیری اظهارنامه برنامه بچین');ai.send();self.pump(lambda:not ai.busy)
        self.assertEqual(len(self.win.events),before);self.assertIn('تاریخ را مشخص کنید',ai.items[-1]['content'])
        ai.prompt.setPlainText('1405/09/01');ai.send();self.pump(lambda:not ai.busy)
        self.assertEqual(len(self.win.events),before+1);self.assertEqual(self.win.events[-1]['date_jalali'],'1405/09/01');messages=endpoints.FakeLM.requests[-1]['messages'];self.assertTrue(any('اظهارنامه' in m['content'] for m in messages if m['role']=='user'))
    def test_application_followup_through_model_connection_and_ui(self):
        endpoints.FakeLM.mode='app_followup';ai=self.win.ai;ai.mode.setCurrentIndex(2);before=len(self.win.events)
        ai.prompt.setPlainText('برای پیگیری اظهارنامه یادآور بساز');ai.send();self.pump(lambda:not ai.busy and not ai.applying)
        self.assertEqual(len(self.win.events),before);self.assertIn('چه تاریخی',ai.items[-1]['content'])
        ai.prompt.setPlainText('1405/09/01');ai.send();self.pump(lambda:not ai.busy and not ai.applying and len(self.win.events)>before)
        self.assertEqual(self.win.events[-1]['date_jalali'],'1405/09/01');self.assertEqual(self.win.events[-1]['title'],'پیگیری اظهارنامه')
    def test_application_settings_change_is_applied_and_persisted(self):
        endpoints.FakeLM.mode='app_settings';ai=self.win.ai;ai.prompt.setPlainText('اعلان هفت ثانیه تنظیم شود');ai.send();self.pump(lambda:self.win.data['settings']['popup_seconds']==7)
        self.assertEqual(self.win.data['settings']['popup_seconds'],7);self.assertFalse(ai.applying)
    def test_disabling_context_clears_old_actions_and_history_but_preserves_draft(self):
        ai=self.win.ai;ai.history=[dict(role='assistant',content='private context')];ai.items=[dict(role='assistant',content='private context')];ai.app_actions=[dict(type='reminder_settings',changes={'popup_seconds':7})];ai.prompt.setPlainText('متن در حال نوشتن');ai.context_check.setChecked(False);self.assertFalse(ai.history);self.assertFalse(ai.items);self.assertFalse(ai.app_actions);self.assertEqual(ai.prompt.toPlainText(),'متن در حال نوشتن');self.assertFalse(self.win.data['settings']['ai_app_access'])
    def test_shared_personal_schedule_survives_calendar_refresh(self):
        from ai_app_actions import capture,collect,normalize_action,execute
        task=self.store.save_record(self.admin,'task',dict(title='کار نمونه شرکت',due_date='1405/08/12',assignee_id=self.admin['id']),'mana');self.win.org.sync();self.pump(lambda:not self.win.org.busy);ctx=collect(capture(self.win),'کار نمونه شرکت');action=normalize_action(dict(type='task_reminder',target='work:'+task['id'],changes={'lead_days':[2,0]}),ctx);result=execute(self.win,[action],ctx,self.client.request);self.assertTrue(result[0]['ok'],str(result));self.pump(lambda:not self.win.org.busy);event=next(e for e in self.win.shared_events if e['shared_id']==task['id']);self.assertEqual(event['lead_days'],[2,0]);self.assertTrue(event['reminder_custom']);self.assertEqual(self.store.record(task['id'])['version'],1)
    def test_ready_prompt_fills_editor_and_requires_placeholder_completion(self):
        ai=self.win.ai;ai.fill_template('schedule');self.assertEqual(ai.mode.currentData(),'app');self.assertEqual(ai.prompt.textCursor().selectedText(),'[عنوان کار]');self.assertFalse(ai.busy);self.assertFalse(endpoints.FakeLM.requests)
        with patch('ai_chat_ui.LMClient') as client:ai.send();client.assert_not_called()
        self.assertIn('کروشه',ai.status.text());ai.prompt.insertPlainText('نمونه');self.assertNotIn('[عنوان کار]',ai.prompt.toPlainText());self.assertFalse(ai.busy)
    def test_new_financial_placeholder_blocks_accidental_send(self):
        ai=self.win.ai;ai.fill_template('cash_transaction');self.assertTrue(ai.prompt.textCursor().hasSelection());self.assertIn('[نام شرکت]',ai.prompt.textCursor().selectedText())
        with patch('ai_chat_ui.make_client') as make:ai.send();make.assert_not_called()
    def test_assistant_can_open_inventory_and_notes(self):
        from ai_app_actions import capture,collect,normalize_action,execute
        for key,module,child in [('products','clients','inventory'),('notes','desk',None)]:
            ctx=collect(capture(self.win),'بخش را باز کن');action=normalize_action(dict(type='open_section',section=key),ctx);result=execute(self.win,[action],ctx,self.client.request);self.assertTrue(result[0]['ok'],str(result));self.assertIs(self.win.tabs.currentWidget(),self.win.modules[module])
            if child:self.assertIs(self.win.clients.pages.currentWidget(),self.win.clients.inventory)
            else:self.assertEqual(self.win.desk.tabs.currentIndex(),1)
    def test_assistant_exports_filtered_report_and_respects_export_permission(self):
        from ai_app_actions import capture,collect,normalize_action,execute
        from openpyxl import load_workbook
        self.store.finance_transaction(self.admin,'mana',dict(direction='income',method='cash',amount='100',date='1405/08/02',reason='نمونه'))
        query='گزارش دریافت شرکت مانا از 1405/08/01 تا 1405/08/30 به صورت اکسل با ستون شماره سند و مبلغ ریال بساز';ctx=collect(capture(self.win),query);raw=dict(type='report_export',company_id='mana',changes=dict(kind='transaction',format='xlsx',start='1405/08/01',end='1405/08/30',columns=['document_no','amount']));action=normalize_action(raw,ctx)
        result=execute(self.win,[action],ctx,self.client.request);self.assertTrue(result[0]['ok'],str(result));files=list((self.root/'reports').glob('*.xlsx'));self.assertEqual(len(files),1);book=load_workbook(files[0],read_only=True);self.assertEqual(list(next(book.active.values)),['شماره سند','مبلغ ریال']);book.close()
        staff=self.store.user(self.store.login('staff','ک')['user']['id']);self.win.session_user=staff
        with self.assertRaises(PermissionError):normalize_action(raw,dict(ctx,actor=staff))
    def test_assistant_exports_pdf_without_leaking_other_company(self):
        from ai_app_actions import capture,collect,normalize_action,execute
        from personalization_ui import request_wait
        self.store.save_record(self.admin,'client',dict(title='طرف مانا'),'mana');self.store.save_record(self.admin,'client',dict(title='طرف آرکا'),'arka');query='گزارش مشتری شرکت مانا به صورت pdf بساز';ctx=collect(capture(self.win),query);action=normalize_action(dict(type='report_export',company_id='mana',changes=dict(kind='client',format='pdf')),ctx)
        with patch('personalization_ui.request_wait',wraps=request_wait) as calls:result=execute(self.win,[action],ctx,self.client.request)
        self.assertTrue(result[0]['ok'],str(result));record_queries=[c.kwargs for c in calls.call_args_list if len(c.args)>1 and c.args[1]=='records'];self.assertTrue(record_queries);self.assertTrue(all(q.get('company')=='mana' for q in record_queries));files=list((self.root/'reports').glob('*.pdf'));self.assertEqual(len(files),1);self.assertTrue(files[0].read_bytes().startswith(b'%PDF'))
    def test_finance_prompt_uses_chat_and_does_not_send(self):
        ai=self.win.ai;ai.fill_template('invoice_calc');self.assertEqual(ai.mode.currentData(),'chat');self.assertIn('تعداد، قیمت',ai.prompt.textCursor().selectedText());self.assertFalse(ai.busy);self.assertFalse(endpoints.FakeLM.requests)
    def test_cloud_settings_and_selected_model_reach_chat_without_leaking_key(self):
        import copy
        saved={};calls=[];ai=self.win.ai
        def load(path,default=None):return copy.deepcopy(saved.get(str(path),default))
        def save(path,value):saved[str(path)]=copy.deepcopy(value)
        class FakeCloud:
            def __init__(self,url,key,timeout):calls.append(('connect',url,key));self.cancelled=False
            def chat(self,model,messages,on_chunk):calls.append(('chat',model));on_chunk('پاسخ نمونه');return 'پاسخ نمونه'
            def close(self):pass
            def cancel(self):self.cancelled=True
        with patch('local_vault.load',side_effect=load),patch('local_vault.save',side_effect=save),patch('avalai_client.AvalAIClient',FakeCloud):
            panel=LMStudioSettings(self.win);panel.cloud_enabled.setChecked(True);panel.cloud_model.setText('model-sample');panel.cloud_key.setText('secret-sample');panel.commit();self.assertNotIn('secret-sample',json.dumps(self.win.data,ensure_ascii=False));ai.mode.setCurrentIndex(0);ai.prompt.setPlainText('سلام');ai.send();self.pump(lambda:not ai.busy);self.assertIn(('chat','model-sample'),calls);self.assertIn('پاسخ نمونه',ai.transcript.toPlainText());panel.deleteLater()
    def test_staff_can_configure_only_their_personal_cloud_key(self):
        from main_ui import apply_preferences
        staff=self.store.user(self.store.login('staff','ک')['user']['id']);staff['memberships'][0]['permissions']={'module.assistant.configure':False,'module.assistant.use':True};self.win.session_user=staff;apply_preferences(self.win)
        with patch('local_vault.load',return_value={}),patch('local_vault.save') as save:
            panel=LMStudioSettings(self.win);self.assertFalse(panel.url.isEnabled());self.assertTrue(panel.cloud_enabled.isEnabled());panel.cloud_enabled.setChecked(True);panel.cloud_model.setText('staff-model');panel.cloud_key.setText('staff-secret');panel.commit();self.assertEqual(save.call_count,1);self.assertEqual(save.call_args.args[1]['model'],'staff-model');panel.deleteLater()
    def test_assignment_template_is_hidden_for_staff_and_does_not_replace_draft(self):
        ai=self.win.ai;staff=self.store.user(self.store.login('staff','ک')['user']['id']);self.win.session_user=staff;apply_preferences(self.win);control=next(c for t,c in ai.template_controls if t['key']=='assign_task');self.assertFalse(control.isVisible());ai.prompt.setPlainText('نوشته خودم');ai.fill_template('assign_task');self.assertEqual(ai.prompt.toPlainText(),'نوشته خودم')

if __name__=='__main__':unittest.main()

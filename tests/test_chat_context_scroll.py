import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtTest import QTest
from unittest.mock import patch
from ai_chat_ui import compact_conversation,previous_search_hint,clarification_request
from lmstudio_client import messages_for
import test_v6_ui as fixtures

class ContextTests(unittest.TestCase):
    def test_short_answer_keeps_only_immediately_requested_task(self):
        history=[{'role':'user','content':'برای ارسال اظهارنامه یادآور بساز'},{'role':'assistant','content':'برای چه تاریخی یادآوری کنم؟'}]
        result=clarification_request(history,'1405/09/01');self.assertIn('اظهارنامه',result);self.assertIn('1405/09/01',result)
        self.assertIn('اظهارنامه',clarification_request(history,'برای 1405/09/01 بذار'))
        self.assertIn('اظهارنامه',clarification_request(history,'برای فردا بذار'));self.assertIn('اظهارنامه',clarification_request(history,'پس‌فردا ثبت کن'))
        self.assertIn('اظهارنامه',clarification_request(history,'پسفردا ثبت کن'))
        history[-1]['content']='لطفا تاریخ را مشخص کنید.';self.assertIn('اظهارنامه',clarification_request(history,'1405/09/01'));history[-1]['content']='برای چه تاریخی یادآوری کنم؟'
        history[-1]['content']='چه تاریخی مدنظر شماست';self.assertIn('اظهارنامه',clarification_request(history,'1405/09/01'));history[-1]['content']='برای چه تاریخی یادآوری کنم؟'
        money=[{'role':'user','content':'پرداخت اجاره شرکت مانا را ثبت کن'},{'role':'assistant','content':'مبلغ چقدره'}];self.assertIn('اجاره',clarification_request(money,'دو میلیون تومان'))
        history.extend([{'role':'user','content':'1405/09/01'},{'role':'assistant','content':'برای کدام شرکت؟'}]);result=clarification_request(history,'مانا');self.assertIn('اظهارنامه',result);self.assertIn('1405/09/01',result);self.assertIn('مانا',result);history=history[:2]
        self.assertEqual(clarification_request(history,'نه'),'نه');self.assertEqual(clarification_request(history,'نمیخوام ادامه بدی'),'نمیخوام ادامه بدی');self.assertEqual(clarification_request(history,'گروه دیگری بساز'),'گروه دیگری بساز')
        self.assertEqual(clarification_request(history,'نمی‌خوام ادامه بدی'),'نمی‌خوام ادامه بدی')
        history[-1]['content']='یادآور ثبت شد.';self.assertEqual(clarification_request(history,'1405/09/01'),'1405/09/01')
    def test_long_assistant_turn_keeps_previous_request(self):
        history=[{'role':'user','content':'اظهارنامه مانا را بررسی کن'},{'role':'assistant','content':'پاسخ'*2000},{'role':'user','content':'برای فردا چطور؟'}]
        messages=messages_for(compact_conversation(history),'system',max_chars=10000)
        self.assertEqual([m['role'] for m in messages],['system','user','assistant','user']);self.assertIn('اظهارنامه',previous_search_hint(history[:-1],history[-1]['content']))
    def test_complete_new_request_does_not_pull_prior_search(self):
        history=[{'role':'user','content':'اظهارنامه قدیمی'}]
        self.assertEqual(previous_search_hint(history,'متن روشن و مستقل '+('الف'*110)),'')

class ScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.V6UiTests.setUpClass();cls.app=fixtures.V6UiTests.app
    setUp=fixtures.V6UiTests.setUp
    tearDown=fixtures.V6UiTests.tearDown
    pump=fixtures.V6UiTests.pump
    def test_new_chat_menu_offers_private_and_group(self):
        actions=[action.text() for action in self.win.chat.new_chat_menu.actions()]
        self.assertEqual(actions,['گفتگوی شخصی','گروه جدید'])
    def test_assistant_stays_on_previous_position_when_not_at_end(self):
        ai=self.win.ai;self.win.tabs.setCurrentWidget(ai);self.win.show();ai.items=[dict(role='user',content='پیام '+str(i)+'\n'+('الف'*300)) for i in range(35)];ai.render();self.app.processEvents();bar=ai.transcript.verticalScrollBar();self.assertGreater(bar.maximum(),0);bar.setValue(bar.maximum()//3);before=bar.value();ai.items.append(dict(role='assistant',content='پاسخ تازه'));ai.render();self.app.processEvents();self.assertEqual(bar.value(),before)
    def test_chat_stays_at_end_and_keeps_position_on_older_messages(self):
        panel=self.win.chat;self.win.tabs.setCurrentWidget(panel);self.win.show();self.app.processEvents();panel.selected={'company':'mana','room':'general'}
        def bubble(item):
            w=QLabel(str(item['seq']));w.setFixedHeight(45);return w
        data=lambda start,end:{'items':[{'seq':i} for i in range(start,end)],'members':[],'has_more':True}
        with patch.object(panel,'bubble',side_effect=bubble):
            panel.render(data(30,60));QTest.qWait(120);bar=panel.area.verticalScrollBar();bar.setValue(bar.maximum());panel.render(data(30,61));QTest.qWait(120);self.assertGreaterEqual(bar.value(),bar.maximum()-1)
            bar.setValue(20);panel.render(data(30,62));QTest.qWait(120);self.assertEqual(bar.value(),20)
            bar.setValue(20);old=bar.value();oldmax=bar.maximum();panel.render(data(10,30),True);QTest.qWait(120);self.assertEqual(bar.value(),old+bar.maximum()-oldmax)

if __name__=='__main__':unittest.main()

import os,sys,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from PySide6.QtWidgets import QApplication,QPushButton
import test_v6_ui as fixtures
from appearance import apply_appearance

class ChatDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        fixtures.V6UiTests.setUp(self);staff=self.store.user(self.store.login('staff','ک')['user']['id']);self.scope='__shared_chat__';self.room=self.store.workspace_group_create(self.admin,self.scope,'گروه آزمون',[staff['id']])['room']
    def tearDown(self):fixtures.V6UiTests.tearDown(self)
    pump=fixtures.V6UiTests.pump
    def test_message_menu_keeps_real_actions_and_reply(self):
        chat=self.win.chat;self.store.chat_send(self.admin,self.scope,self.room,'پیام آزمایشی');message=self.store.chat_list(self.admin,self.scope,self.room)['items'][0];bubble=chat.bubble(message)
        buttons=[b for b in bubble.findChildren(QPushButton) if b.accessibleName()=='گزینه‌های پیام'];self.assertEqual(len(buttons),1);menu=buttons[0].message_menu;names=[a.text() for a in menu.actions()]
        for name in ('پاسخ','ذخیره','سنجاق','ساخت کار','حذف برای همه'):self.assertIn(name,names)
        next(a for a in menu.actions() if a.text()=='پاسخ').trigger();self.assertEqual(chat.reply_to,message['id']);bubble.deleteLater()
    def test_initial_multi_company_user_sees_exactly_one_saved_chat(self):
        from unittest.mock import patch
        user=self.store.save_user(self.admin,dict(username='three_company_ui',password='1',fullname='کاربر سه شرکت',memberships=[dict(company_id=co,role='employee') for co in ('mana','airia','arka')]))
        actor=self.store.user(user['id']);chat=self.win.chat;chat.selected=None;updates={'rooms':self.store.chat_rooms(actor),'items':[],'meetings':[],'cursor':0}
        with patch.object(chat,'run',return_value=False):chat.receive((updates,None,None))
        self.assertEqual(chat.room_list.count(),0);self.assertIn('پیام‌های ذخیره‌شده',[a.text() for a in chat.new_chat_menu.actions()])
    def test_messages_align_by_sender(self):
        chat=self.win.chat;staff=self.store.user(self.store.login('staff','ک')['user']['id'])
        self.store.chat_send(self.admin,self.scope,self.room,'پیام من');self.store.chat_send(staff,self.scope,self.room,'پاسخ همکار')
        for m in self.store.chat_list(self.admin,self.scope,self.room)['items']:
            bubble=chat.bubble(m);bubble.resize(700,120);bubble.show();self.app.processEvents()
            panel=next(bubble.layout().itemAt(i).widget() for i in range(bubble.layout().count()) if bubble.layout().itemAt(i).widget())
            if m['author']==self.admin['id']:self.assertGreater(panel.x()+panel.width()/2,bubble.width()/2)
            else:self.assertLess(panel.x()+panel.width()/2,bubble.width()/2)
            bubble.hide();bubble.deleteLater()
    def test_stale_refresh_keeps_new_room_but_revoked_room_is_cleared(self):
        chat=self.win.chat;staff=self.store.user(self.store.login('staff','ک')['user']['id']);entry=self.store.workspace_direct(self.admin,self.scope,staff['id']);chat.selected=entry
        updates={'rooms':[],'items':[],'meetings':[],'cursor':0}
        chat.receive((updates,None,None));self.assertEqual(chat.selected['room'],entry['room'])
        chat.receive((updates,None,entry));self.assertIsNone(chat.selected);self.assertEqual(chat.messages,[])
    def test_profile_image_is_cropped_to_a_circle(self):
        from PySide6.QtGui import QPixmap,QColor
        from chat_ui import circular_avatar
        p=QPixmap(80,50);p.fill(QColor('#BB3311'));result=circular_avatar(p,48).toImage()
        self.assertEqual(result.pixelColor(0,0).alpha(),0);self.assertEqual(result.pixelColor(47,0).alpha(),0);self.assertEqual(result.pixelColor(24,24).alpha(),255)
    def test_theme_changes_preserve_accessible_actions(self):
        chat=self.win.chat
        for mode in ('light','dark'):
            self.win.data['settings'].update(theme_preset='glass_mist',theme=mode);apply_appearance(self.win.data['settings']);chat.apply_theme();self.assertEqual(chat._chat_theme_key,('glass_mist',mode));self.assertTrue(chat.compose.placeholderText());self.assertTrue({'attachment','emoji','poll','meeting','schedule','schedule_list','delete'}.issubset({key for _,key in chat._chat_actions}))
            self.assertTrue(all(b.toolTip() and b.accessibleName() for b,_ in chat._chat_actions))

if __name__=='__main__':unittest.main(verbosity=2)

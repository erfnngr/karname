import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import test_ai_app_actions as fixtures
from ai_app_actions import capture,collect,normalize_action,execute
from ai_language import time_window
from storage import today_j,jformat,normalize
import jdatetime

class DirectAliasTests(unittest.TestCase):
    def test_surname_meeting_and_duplicate_surname(self):
        x=fixtures.SharedActionTests('test_chat_group_can_be_created_without_invited_members');x.setUp()
        try:
            p=x.s.save_user(x.admin,dict(username='pezande',password='1',fullname='دکتر پزنده',memberships=[dict(company_id='mana',role='employee')]))
            direct=x.s.workspace_direct(x.s.user(x.staff_id),'__shared_chat__',p['id'])
            q='برای شنبه با اقای پزنده ساعت 10 صبح با موضوع بد بودن وضعیت مملکت جلسه بذار'
            ctx=collect(capture(x.o),q);rid=next(k for k,r in ctx['rooms'].items() if r['room']==direct['room'])
            day=time_window(q,today_j().togregorian())[0];date=normalize(jformat(jdatetime.date.fromgregorian(date=day)))
            raw=dict(type='chat_special',room_id=rid,changes=dict(kind='meeting',title='بد بودن وضعیت مملکت',date=date,time='10:00'))
            result=execute(x.o,[normalize_action(raw,ctx)],ctx,x.client.request);self.assertTrue(result[0]['ok'],str(result))
            x.s.save_user(x.admin,dict(username='pezande2',password='1',fullname='علی پزنده',memberships=[dict(company_id='mana',role='employee')]))
            ctx=collect(capture(x.o),q);rid=next(k for k,r in ctx['rooms'].items() if r['room']==direct['room']);raw['room_id']=rid
            with self.assertRaises(ValueError):normalize_action(raw,ctx)
        finally:x.tearDown()

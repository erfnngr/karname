import unittest
from datetime import date,timedelta
from unittest.mock import Mock
from check_reminders import due


class CheckReminderTest(unittest.TestCase):
    def test_exact_leads_dedup_and_status(self):
        today=date(2026,3,21);base={'company_id':'mana','id':'a','number':'1','due_date':'1405/01/06','status':'pending'}
        settings={'reminder_enabled':True,'check_reminders':True,'check_lead_days':[5,0]}
        rows=[base,dict(base,id='b',status='cleared'),dict(base,id='c',due_date='1405/01/07')]
        found=due(rows,settings,{},'u',today);self.assertEqual(len(found),1);self.assertEqual(found[0][0],5)
        self.assertFalse(due(rows,settings,{found[0][2]:True},'u',today));self.assertEqual(len(due(rows,settings,{found[0][2]:True},'other',today)),1)
        self.assertFalse(due(rows,dict(settings,check_reminders=False),{},'u',today));self.assertFalse(due(rows,settings,{},'u',date(2026,3,28)))
    def test_popup_is_deduplicated_only_after_it_is_shown_and_identity_checked(self):
        import jdatetime
        from v8_controller import V8Controller
        owner=Mock();owner.org.client.url='http://local';owner.org.client.token='token';owner.session_user={'id':'u','global_role':'group_admin'};owner._locking=False;owner._exit_pending=False;owner._exit_approved=False;owner._popups=[];owner._popup_queue=[];owner.data={'settings':{'reminder_enabled':True,'check_reminders':True,'check_lead_days':[1]}}
        d=jdatetime.date.fromgregorian(date=date.today()+timedelta(days=1));rows=[{'company_id':'mana','company_name':'مانا','id':'one','number':'10','due_date':f'{d.year}/{d.month:02}/{d.day:02}','status':'pending','direction':'received'}];controller=Mock();controller.owner=owner
        V8Controller.checks_finished(controller,rows,None,('http://local','wrong'));owner.popup.assert_not_called()
        V8Controller.checks_finished(controller,rows,None,('http://local','token'));self.assertEqual(owner.popup.call_count,1);owner.popup.call_args.kwargs['on_shown']();V8Controller.checks_finished(controller,rows,None,('http://local','token'));self.assertEqual(owner.popup.call_count,1)
        owner.data['finance_check_alerts']={};owner.session_user={'id':'u','global_role':'employee','memberships':[{'company_id':'mana','role':'employee','permissions':{'module.clients.view':True,'module.finance.view':False}}]};V8Controller.checks_finished(controller,rows,None,('http://local','token'));self.assertEqual(owner.popup.call_count,1)

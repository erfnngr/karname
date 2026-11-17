import unittest
from datetime import date,datetime,timedelta,timezone
from types import SimpleNamespace
import jdatetime
from assistant_awareness import alerts,weather_context,review_items,review_alerts
from storage import jformat

class AwarenessTests(unittest.TestCase):
    def test_forecast_alert_and_daily_deduplication(self):
        today=date.today();tomorrow=today+timedelta(days=1)
        event={'id':'one','title':'جلسه حضوری','date_jalali':jformat(jdatetime.date.fromgregorian(date=tomorrow))}
        forecast={'days':[{'date':tomorrow.isoformat(),'code':61,'description':'بارانی'}]}
        results=alerts([event],forecast,{},today)
        self.assertEqual(len(results),1);self.assertIn('تهران',results[0][1]);self.assertFalse(alerts([event],forecast,{results[0][0]:True},today))
        self.assertFalse(alerts([dict(event,title='کار اداری')],forecast,{},today))
    def test_overdue_and_done(self):
        today=date.today();before=today-timedelta(days=2)
        event={'id':'two','title':'پیگیری','date_jalali':jformat(jdatetime.date.fromgregorian(date=before))}
        self.assertEqual(len(alerts([event],None,{},today)),1)
        self.assertFalse(alerts([dict(event,done=True)],None,{},today))
    def test_stale_weather_is_not_used(self):
        stamp=datetime.now(timezone.utc)-timedelta(hours=7)
        service=SimpleNamespace(enabled=True,data={'current':{},'days':[]},checked_at=stamp,cached=True)
        self.assertIsNone(weather_context(service))
    def test_review_uses_authorized_records_and_deduplicates(self):
        finance={'id':'one','global_role':'employee','memberships':[{'company_id':'mana','role':'finance','permissions':{}}]}
        records=[{'id':'a','company_id':'mana','kind':'tax_case','payload':{'title':'پرونده اول','status':'draft','due_date':''}},{'id':'b','company_id':'arka','kind':'tax_case','payload':{'title':'محرمانه','status':'draft','due_date':''}},{'id':'c','company_id':'mana','kind':'tax_case','payload':{'title':'پرونده دوم','status':'submitted','reference':''}}]
        self.assertEqual({x['id'] for x in review_items(records,finance)},{'a','c'})
        results=review_alerts(records,finance,{});self.assertEqual(len(results),2)
        self.assertFalse(review_alerts(records,finance,{k:True for k,_ in results}))
        self.assertFalse(review_items(records,{'global_role':'employee','memberships':[]}))

if __name__=='__main__':unittest.main()

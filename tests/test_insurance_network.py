import tempfile,unittest
from pathlib import Path
from org_store import Store,DomainError
from org_http import RunningServer
from org_client import Client

class InsuranceNetworkTests(unittest.TestCase):
    def test_network_record_and_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'server';store=Store(root);store.bootstrap('admin','pass','مدیر');server=RunningServer(root,'127.0.0.1',0);client=Client('http://127.0.0.1:'+str(server.port))
            try:
                client.login('admin','pass')
                def save(kind,payload):return client.request('records',dict(kind=kind,company='mana',payload=payload))
                workshop=save('insurance_workshop',dict(title='کارگاه',workshop_code='001'))
                employee=save('employee',dict(title='کارمند',employee_code='001'))
                profile=save('insurance_employee',dict(title='کارمند',employee_id=employee['id'],workshop_id=workshop['id']))
                draft=save('insurance_list',dict(title='لیست',workshop_id=workshop['id'],period='1405/08',list_no='1',rows=[dict(profile_id=profile['id'],days='30',daily_wage='1000',daily_seniority='100',spouse_benefit='500',insured_benefits='2500',non_insured_benefits='2000',unemployment_applies=True)]))
                rule=save('insurance_rules',dict(title='آزمایشی',rules_version='1',source='آزمایشی',effective_from='1405/01/01',effective_to='1405/12/29',worker_rate='7',employer_rate='20',unemployment_rate='3',minimum_daily='100',maximum_daily='10000',approved=True))
                result=save('insurance_calculation',dict(title='محاسبه',insurance_list_id=draft['id'],rules_id=rule['id']))
                self.assertEqual(result['payload']['result']['totals']['insurance_total'],'10800')
                store.save_user(client.user,dict(username='worker',password='pass',fullname='همکار',memberships=[dict(company_id='mana',role='employee')]))
                client.login('worker','pass')
                self.assertEqual(client.request('records',kind='insurance_employee',company='mana')['total'],0)
                with self.assertRaises(DomainError):client.request('record',id=profile['id'])
                with self.assertRaises(DomainError):client.request('record',id=result['id'])
                delta=client.request('workspace/records-delta',dict(after=0,known=[]))
                self.assertNotIn(profile['id'],{r['id'] for r in delta['items']});self.assertNotIn(result['id'],{r['id'] for r in delta['items']})
                with self.assertRaises(DomainError):client.request('history',id=profile['id'])
            finally:client.session.close();server.close()

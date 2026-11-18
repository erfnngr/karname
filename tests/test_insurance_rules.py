import tempfile,unittest
from pathlib import Path
from org_store import Store,DomainError

class InsuranceRulesTests(unittest.TestCase):
    def test_version_immutable_and_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d));actor=store.bootstrap('admin','pass','مدیر')
            p=dict(title='آزمایشی',rules_version='test-1',source='منبع آزمایشی',effective_from='۱۴۰۵/۰۱/۰۱',effective_to='۱۴۰۵/۱۲/۲۹',worker_rate='۷',employer_rate='۲۰',unemployment_rate='۳',minimum_daily='۱۰۰',maximum_daily='۱۰۰۰۰',approved=True)
            record=store.save_record(actor,'insurance_rules',p,'mana')
            self.assertEqual(record['payload']['worker_rate'],'7')
            with self.assertRaises(DomainError):store.save_record(actor,'insurance_rules',p,'mana')
            with self.assertRaises(DomainError):store.save_record(actor,'insurance_rules',p,'mana',record['id'],record['version'])
            with self.assertRaises(DomainError):store.save_record(actor,'insurance_rules',{**p,'rules_version':'x','maximum_daily':'1'},'mana')
            with self.assertRaises(DomainError):store.save_record(actor,'insurance_rules',{**p,'rules_version':'x','effective_to':'۱۴۰۴/۱۲/۲۹'},'mana')
            uid=store.save_user(actor,dict(username='worker',password='pass',fullname='همکار',memberships=[dict(company_id='mana',role='employee')]))['id']
            employee=store.user(uid)
            self.assertEqual(store.list_records(employee,'insurance_rules','mana')['total'],0)
            with self.assertRaises(DomainError):store.save_record(employee,'insurance_rules',{**p,'rules_version':'y'},'mana')

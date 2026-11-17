import tempfile
import unittest
from pathlib import Path
from org_store import Store, DomainError


class InsuranceWorkshopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.admin=self.store.bootstrap('admin','test-password','مدیر آزمون')
        self.payload={'title':'کارگاه آزمایشی','workshop_code':'۰۰۰۱۲۳','contract_row':'۰۰۱','national_id':'۰۰۱۲۳۴'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_zeroes_duplicates_company_scope_and_version(self):
        record=self.store.save_record(self.admin,'insurance_workshop',self.payload,'mana')
        self.assertEqual(record['payload']['workshop_code'],'000123')
        self.assertEqual(record['payload']['national_id'],'001234')
        with self.assertRaises(DomainError):self.store.save_record(self.admin,'insurance_workshop',self.payload,'mana')
        self.store.save_record(self.admin,'insurance_workshop',self.payload,'arka')
        updated=self.store.save_record(self.admin,'insurance_workshop',{**self.payload,'branch':'نمونه'},'mana',record['id'],record['version'])
        self.assertEqual(updated['version'],record['version']+1)
        with self.assertRaises(DomainError):self.store.save_record(self.admin,'insurance_workshop',self.payload,'mana',record['id'],record['version'])

    def test_employee_cannot_read_or_create_without_authority(self):
        self.store.save_record(self.admin,'insurance_workshop',self.payload,'mana')
        uid=self.store.save_user(self.admin,dict(username='worker',password='test-password',fullname='همکار',memberships=[dict(company_id='mana',role='employee')]))['id']
        actor=self.store.user(uid)
        self.assertEqual(self.store.list_records(actor,'insurance_workshop','mana')['total'],0)
        with self.assertRaises(DomainError):self.store.save_record(actor,'insurance_workshop',self.payload,'mana')

    def test_invalid_identifiers_are_rejected(self):
        with self.assertRaises(DomainError):self.store.save_record(self.admin,'insurance_workshop',{**self.payload,'workshop_code':'00x12'},'mana')

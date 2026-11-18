import tempfile
import unittest
from pathlib import Path
from org_store import Store, DomainError


class InsuranceEmployeeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name));self.admin=self.s.bootstrap('admin','test-password','مدیر')
        self.workshop=self.s.save_record(self.admin,'insurance_workshop',{'title':'کارگاه','workshop_code':'۰۰۱'},'mana')
        self.employee=self.s.save_record(self.admin,'employee',{'title':'کارمند آزمونی','employee_code':'001'},'mana')
        self.p={'title':'بیمه کارمند','workshop_id':self.workshop['id'],'employee_id':self.employee['id'],'national_id':'۰۰۱۲۳۴۵۶۷۸','insurance_number':'۰۰۰۰۷','start_date':'۱۴۰۵/۰۱/۰۱'}
    def tearDown(self):self.tmp.cleanup()
    def test_links_string_identifiers_and_uniqueness(self):
        record=self.s.save_record(self.admin,'insurance_employee',self.p,'mana')
        self.assertEqual(record['payload']['national_id'],'0012345678');self.assertEqual(record['payload']['insurance_number'],'00007')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'insurance_employee',self.p,'mana')
        other=self.s.save_record(self.admin,'employee',{'title':'فرد دیگر','employee_code':'002'},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'insurance_employee',{**self.p,'employee_id':other['id']},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'insurance_employee',{**self.p,'employee_id':other['id']},'mana',record['id'],record['version'])
    def test_cross_company_and_unprivileged_user_denied(self):
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'insurance_employee',self.p,'arka')
        self.s.save_record(self.admin,'insurance_employee',self.p,'mana')
        uid=self.s.save_user(self.admin,dict(username='worker',password='test-password',fullname='همکار',memberships=[dict(company_id='mana',role='employee')]))['id'];actor=self.s.user(uid)
        self.assertEqual(self.s.list_records(actor,'insurance_employee','mana')['total'],0)
        with self.assertRaises(DomainError):self.s.save_record(actor,'insurance_employee',self.p,'mana')
    def test_bad_dates_and_identifiers_rejected(self):
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'insurance_employee',{**self.p,'end_date':'۱۴۰۴/۱۲/۲۹'},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'insurance_employee',{**self.p,'insurance_number':'A100'},'mana')
    def test_separate_names_and_issue_date_are_saved(self):
        record=self.s.save_record(self.admin,'insurance_employee',{**self.p,'first_name':'نمونه','last_name':'آزمایشی','issue_date':'۱۳۸۰/۰۱/۰۱'},'mana')
        self.assertEqual(record['payload']['first_name'],'نمونه');self.assertEqual(record['payload']['last_name'],'آزمایشی');self.assertEqual(record['payload']['issue_date'],'1380/01/01')
    def test_referenced_workshop_and_employee_cannot_be_archived(self):
        self.s.save_record(self.admin,'insurance_employee',self.p,'mana')
        for record in (self.employee,self.workshop):
            with self.assertRaises(DomainError):self.s.delete_record(self.admin,record['id'],record['version'])

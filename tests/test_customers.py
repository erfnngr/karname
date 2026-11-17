import sys,tempfile,unittest,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from customer_data import customer,invoice,buyer_snapshot
from org_store import Store,DomainError

def sample_invoice(client_id,number='INV-1'):
    return dict(title='فاکتور نمونه',client_id=client_id,number=number,date='1405/08/06',due_date='1405/08/20',lines=[dict(description='خدمت نمونه',quantity='2',unit='خدمت',unit_price='1250000',discount='500000',tax_rate='10')])

class CustomerDataTests(unittest.TestCase):
    def test_ids_keep_leading_zeroes_and_incomplete_files_can_be_saved(self):
        p=customer(dict(title='شخص نمونه',customer_type='حقیقی',national_id='۰۰۱۲۳۴۵۶۷۸',postal_code='۱۲۳۴۵۶۷۸۹۰'));self.assertEqual(p['national_id'],'0012345678');self.assertEqual(p['postal_code'],'1234567890');self.assertEqual(customer(dict(title='پرونده اولیه'))['customer_type'],'نامشخص')
    def test_invalid_postal_email_and_large_values_are_rejected(self):
        for value in (dict(postal_code='123'),dict(email='broken'),dict(economic_code='abc'),dict(title='x'*501)):
            with self.assertRaises(ValueError):customer(dict(title='نمونه',**value) if 'title' not in value else value)
    def test_invoice_arithmetic_is_decimal_per_line_and_user_rate(self):
        p=invoice(sample_invoice('sample'));self.assertEqual(p['totals'],dict(subtotal='2500000',discount='500000',tax='200000',total='2200000'));self.assertEqual(p['lines'][0]['total'],'2200000')
        v=sample_invoice('sample');v['lines'][0].update(quantity='۳',unit_price='۱۰۰',discount='۰',tax_rate='۰');self.assertEqual(invoice(v)['totals']['total'],'300')
    def test_global_discount_is_allocated_before_each_tax_and_charge_has_own_rate(self):
        p=sample_invoice('sample');p['lines']=[dict(description='اول',quantity='1',unit_price='100',discount='0',tax_rate='10'),dict(description='دوم',quantity='1',unit_price='200',discount='0',tax_rate='0')];p.update(invoice_discount_mode='percent',invoice_discount_value='10',additional_charge='50',charge_tax_rate='20')
        result=invoice(p);self.assertEqual([x['invoice_discount_share'] for x in result['lines']],['10','20']);self.assertEqual(result['totals'],{'subtotal':'300','discount':'30','tax':'19','total':'339','additional_charge':'50','charge_tax':'10'});self.assertEqual(invoice(result)['totals'],result['totals'])
        p.update(invoice_discount_mode='amount',invoice_discount_value='301')
        with self.assertRaises(ValueError):invoice(p)
    def test_global_discount_rounding_keeps_all_rials(self):
        p=sample_invoice('sample');p['lines']=[dict(description=str(i),quantity='1',unit_price='1',tax_rate='0') for i in range(3)];p.update(invoice_discount_mode='amount',invoice_discount_value='2')
        result=invoice(p);self.assertEqual([x['invoice_discount_share'] for x in result['lines']],['1','1','0']);self.assertEqual(result['totals']['total'],'1')
    def test_line_percentage_discount_is_recomputed_and_not_combined_with_fixed_discount(self):
        p=sample_invoice('sample');p['lines'][0].update(quantity='1',unit_price='1000',discount='0',discount_rate='10',tax_rate='10')
        result=invoice(p);self.assertEqual(result['lines'][0]['discount'],'100');self.assertEqual(result['totals']['total'],'990');self.assertEqual(invoice(result)['totals'],result['totals'])
        p['lines'][0]['discount']='5'
        with self.assertRaises(ValueError):invoice(p)
    def test_invoice_rejects_negative_nonfinite_zero_quantity_or_excessive_discount(self):
        for field,value in [('quantity','0'),('unit_price','-1'),('unit_price','NaN'),('tax_rate','101'),('discount','2500001')]:
            p=sample_invoice('sample');p['lines'][0][field]=value
            with self.assertRaises(ValueError,msg=field):invoice(p)

class CustomerStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.admin=self.store.bootstrap('admin','Fixture-Password-123','مدیر');self.client=self.store.save_record(self.admin,'client',dict(title='شرکت نمونه',customer_type='حقوقی',national_id='00123456789',economic_code='123456789012',postal_code='1234567890',address='نشانی نمونه'),'mana')
    def tearDown(self):self.tmp.cleanup()
    def test_customer_permission_is_independent_and_grant_applies_to_fresh_session(self):
        staff=self.store.save_user(self.admin,dict(username='staff',password='Fixture-Password-123',fullname='کارمند',memberships=[dict(company_id='mana',role='employee')]))
        p=dict(self.client['payload'],assignee_id=staff['id']);self.client=self.store.save_record(self.admin,'client',p,'mana',self.client['id'],self.client['version']);self.assertFalse(self.store.readable(self.store.user(staff['id']),self.client))
        self.store.save_permissions(self.admin,staff['id'],'mana',{'module.clients.view':True,'module.clients.create':True});actor=self.store.user(staff['id']);self.assertTrue(self.store.readable(actor,self.client));created=self.store.save_record(actor,'client',dict(title='مشتری کارمند'),'mana');self.assertEqual(created['owner_id'],staff['id'])
        with self.assertRaises(DomainError):self.store.save_record(actor,'invoice',sample_invoice(self.client['id']),'mana')
    def test_buyer_snapshot_is_authoritative_and_old_invoice_stays_fixed(self):
        p=sample_invoice(self.client['id']);p['customer_snapshot']={'title':'مقدار جعلی'};p['totals']={'total':'1'};saved=self.store.save_record(self.admin,'invoice',p,'mana');self.assertEqual(saved['payload']['customer_snapshot']['title'],'شرکت نمونه');self.assertEqual(saved['payload']['totals']['total'],'2200000')
        changed=dict(self.client['payload'],title='نام تازه',address='نشانی تازه');self.client=self.store.save_record(self.admin,'client',changed,'mana',self.client['id'],self.client['version']);edited=self.store.save_record(self.admin,'invoice',dict(saved['payload'],notes='ویرایش توضیح'),'mana',saved['id'],saved['version']);self.assertEqual(edited['payload']['customer_snapshot']['address'],'نشانی نمونه')
        refreshed=self.store.save_record(self.admin,'invoice',dict(edited['payload'],refresh_customer=True),'mana',edited['id'],edited['version']);self.assertEqual(refreshed['payload']['customer_snapshot']['address'],'نشانی تازه');self.assertNotIn('refresh_customer',refreshed['payload'])
        other=self.store.save_record(self.admin,'invoice',sample_invoice(self.client['id'],'INV-2'),'mana');self.assertEqual(other['payload']['customer_snapshot']['title'],'نام تازه')
    def test_cross_company_customer_reference_is_rejected(self):
        for kind,p in [('invoice',sample_invoice(self.client['id'])),('tax_job',dict(title='کار مالیاتی',client_id=self.client['id'],due_date='1405/08/20',status='draft'))]:
            with self.assertRaises(DomainError):self.store.save_record(self.admin,kind,p,'arka')
    def test_duplicate_identity_and_invoice_number_and_stale_edits_are_rejected(self):
        with self.assertRaises(DomainError):self.store.save_record(self.admin,'client',dict(title='تکراری',national_id='00123456789'),'mana')
        self.store.save_record(self.admin,'invoice',sample_invoice(self.client['id']),'mana')
        with self.assertRaises(DomainError):self.store.save_record(self.admin,'invoice',sample_invoice(self.client['id']),'mana')
        with self.assertRaises(DomainError):self.store.save_record(self.admin,'client',dict(self.client['payload'],title='تغییر'),'mana',self.client['id'],0)
    def test_tax_job_copies_tax_identity_and_period_and_is_audited(self):
        r=self.store.save_record(self.admin,'tax_job',dict(title='اظهارنامه مشتری',client_id=self.client['id'],due_date='1405/08/20',status='draft',period='1405'),'mana');self.assertEqual(r['payload']['customer_snapshot']['economic_code'],'123456789012');self.assertEqual(r['payload']['period'],'1405');self.assertEqual(self.store.record(r['id'])['version'],1)

if __name__=='__main__':unittest.main(verbosity=2)

import tempfile,unittest
from org_store import Store,DomainError

class FinanceStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(self.tmp.name);self.admin=self.s.bootstrap('admin','password','مدیر');self.buyer=self.s.save_record(self.admin,'client',{'title':'مشتری'},'mana')
    def tearDown(self):self.tmp.cleanup()
    def invoice(self,number,check):
        return {'title':'فاکتور','client_id':self.buyer['id'],'number':number,'date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[{'kind':'check','amount':'600','check_id':check}]}
    def test_next_invoice_number_is_read_only_and_separate_by_type(self):
        def preview(kind):return self.s.finance_next_invoice_number(self.admin,'mana',kind)['number']
        self.assertEqual(preview('فاکتور فروش'),'100');self.assertEqual(preview('فاکتور فروش'),'100')
        self.s.save_record(self.admin,'invoice',{'title':'فروش','client_id':self.buyer['id'],'number':'__AUTO__','date':'1405/08/01','document_type':'فاکتور فروش','status':'draft','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}]},'mana')
        self.assertEqual(preview('فاکتور فروش'),'101');self.assertEqual(preview('پیش‌فاکتور'),'100')
        with self.assertRaises(DomainError):preview('نامعتبر')
    def test_transaction_request_id_prevents_duplicate(self):
        payload={'direction':'expense','method':'cash','amount':'1000','date':'1405/08/01','reason':'اجاره','request_id':'a'*32}
        first=self.s.finance_transaction(self.admin,'mana',payload);second=self.s.finance_transaction(self.admin,'mana',payload);self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate'])
        with self.assertRaises(DomainError):self.s.finance_transaction(self.admin,'mana',dict(payload,amount='2000'))
        self.assertEqual(len(self.s.finance_list(self.admin,'mana')['transactions']),1)
    def test_check_assignment_reuse_and_restore(self):
        check=self.s.finance_check_add(self.admin,'mana','123','بانک','600','1405/08/10')['id']
        first=self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        self.assertEqual(first['payload']['settlement_summary']['uncollected'],'1000')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'invoice',self.invoice('2',check),'mana')
        self.s.delete_record(self.admin,first['id'],first['version'])
        second=self.s.save_record(self.admin,'invoice',self.invoice('2',check),'mana')
        with self.assertRaises(DomainError):self.s.workspace_trash(self.admin,kind='record',id=first['id'],version=first['version']+1,restore=True)
        self.assertEqual(self.s.finance_list(self.admin,'mana')['checks'][0]['invoice_id'],second['id'])
    def test_cross_company_account_and_wrong_check_amount_rejected(self):
        check=self.s.finance_check_add(self.admin,'arka','123','بانک','600','1405/08/10')['id']
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        check=self.s.finance_check_add(self.admin,'mana','124','بانک','700','1405/08/10')['id']
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
    def test_auto_document_and_invoice_sequences(self):
        def draft(kind):return {'title':'فاکتور','client_id':self.buyer['id'],'number':'__AUTO__','date':'1405/08/01','document_type':kind,'status':'draft','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}]}
        a=self.s.save_record(self.admin,'invoice',draft('پیش‌فاکتور'),'mana');b=self.s.save_record(self.admin,'invoice',draft('فاکتور فروش'),'mana');c=self.s.save_record(self.admin,'invoice',draft('فاکتور فروش'),'mana')
        self.assertEqual([x['payload']['number'] for x in (a,b,c)],['100','100','101']);self.assertEqual([x['payload']['document_no'] for x in (a,b,c)],['100','101','102'])
        tx=self.s.finance_transaction(self.admin,'mana',{'direction':'income','method':'cash','amount':'100','date':'1405/08/02','reason':'دریافت وجه','customer_id':self.buyer['id']});self.assertEqual(tx['document_no'],'103')
        row=self.s.finance_list(self.admin,'mana')['transactions'][0];self.s.finance_transaction(self.admin,'mana',{'direction':'expense','method':'cash','amount':'50','date':'1405/08/03','reason':'اصلاح'},id=tx['id'],version=row['version'])
        self.assertEqual(self.s.finance_list(self.admin,'mana')['transactions'][0]['document_no'],'103')
        with self.assertRaises(DomainError):self.s.finance_transaction(self.admin,'mana',{'direction':'income','method':'cash','amount':'1','date':'1405/08/03','reason':'قدیمی'},id=tx['id'],version=row['version'])
    def test_purchase_requires_outgoing_check(self):
        check=self.s.finance_check_add(self.admin,'mana','111','بانک','600','1405/08/10',direction='issued')['id']
        payload=self.invoice('1',check);payload['document_type']='فاکتور خرید'
        record=self.s.save_record(self.admin,'invoice',payload,'mana');self.assertEqual(self.s.finance_list(self.admin,'mana')['checks'][0]['invoice_id'],record['id'])
    def test_balance_excludes_pending_check_and_counts_cash_transaction(self):
        check=self.s.finance_check_add(self.admin,'mana','333','بانک','600','1405/08/10')['id'];self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        self.s.finance_transaction(self.admin,'mana',{'direction':'income','method':'cash','amount':'200','date':'1405/08/02','reason':'دریافت','customer_id':self.buyer['id']})
        self.assertEqual(self.s.finance_list(self.admin,'mana')['balances'][self.buyer['id']],'800')
    def test_allocated_transaction_is_bounded_and_prevents_invoice_deletion(self):
        payload={'title':'فروش','client_id':self.buyer['id'],'number':'1','date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]}
        invoice=self.s.save_record(self.admin,'invoice',payload,'mana')
        payment={'direction':'income','method':'cash','amount':'600','date':'1405/08/02','reason':'پرداخت','customer_id':self.buyer['id'],'invoice_id':invoice['id']}
        self.s.finance_transaction(self.admin,'mana',payment)
        data=self.s.finance_list(self.admin,'mana');self.assertEqual(data['balances'][self.buyer['id']],'400');self.assertEqual(data['transactions'][0]['invoice_id'],invoice['id'])
        with self.assertRaises(DomainError):self.s.finance_transaction(self.admin,'mana',dict(payment,amount='401'))
        with self.assertRaises(DomainError):self.s.delete_record(self.admin,invoice['id'],invoice['version'])
    def test_concurrent_allocations_cannot_overpay_invoice(self):
        from concurrent.futures import ThreadPoolExecutor
        payload={'title':'فروش','client_id':self.buyer['id'],'number':'1','date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]}
        invoice=self.s.save_record(self.admin,'invoice',payload,'mana')
        payment={'direction':'income','method':'cash','amount':'600','date':'1405/08/02','reason':'پرداخت','customer_id':self.buyer['id'],'invoice_id':invoice['id']}
        def write(_):
            try:self.s.finance_transaction(self.admin,'mana',payment);return True
            except DomainError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,range(2)))
        self.assertEqual(sorted(results),[False,True]);self.assertEqual(self.s.finance_list(self.admin,'mana')['balances'][self.buyer['id']],'400')
    def test_split_payment_allocates_two_invoices_without_double_counting(self):
        base={'title':'فروش','client_id':self.buyer['id'],'date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]}
        one=self.s.save_record(self.admin,'invoice',dict(base,number='1'),'mana');two=self.s.save_record(self.admin,'invoice',dict(base,number='2'),'mana')
        payload={'direction':'income','method':'cash','amount':'1100','date':'1405/08/02','reason':'پرداخت','customer_id':self.buyer['id'],'allocations':[{'invoice_id':one['id'],'amount':'600'},{'invoice_id':two['id'],'amount':'400'}]}
        tx=self.s.finance_transaction(self.admin,'mana',payload);data=self.s.finance_list(self.admin,'mana');self.assertEqual(data['balances'][self.buyer['id']],'900');by_id={r['id']:r for r in data['invoice_documents']};self.assertEqual(by_id[one['id']]['remaining_after_allocations'],'400');self.assertEqual(by_id[two['id']]['remaining_after_allocations'],'600');self.assertEqual(len(data['transactions'][0]['allocations']),2)
        with self.assertRaises(DomainError):self.s.delete_record(self.admin,two['id'],two['version'])
        with self.assertRaises(DomainError):self.s.finance_transaction(self.admin,'mana',dict(payload,allocations=[{'invoice_id':one['id'],'amount':'1001'}]))
        old=data['transactions'][0];self.s.finance_transaction(self.admin,'mana',dict(payload,allocations=[]),id=tx['id'],version=old['version']);self.assertFalse(self.s.finance_list(self.admin,'mana')['transactions'][0]['allocations'])
    def test_legacy_single_invoice_payment_is_migrated_once(self):
        payload={'title':'فروش','client_id':self.buyer['id'],'number':'1','date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]}
        invoice=self.s.save_record(self.admin,'invoice',payload,'mana');tx=self.s.finance_transaction(self.admin,'mana',{'direction':'income','method':'cash','amount':'300','date':'1405/08/02','reason':'پرداخت','customer_id':self.buyer['id'],'invoice_id':invoice['id']})
        with self.s.db(True) as c:c.execute('DROP TABLE finance_allocations')
        self.s=Store(self.tmp.name);self.s=Store(self.tmp.name);rows=self.s.finance_list(self.admin,'mana');self.assertEqual(rows['balances'][self.buyer['id']],'700');self.assertEqual(rows['transactions'][0]['allocations'],[{'invoice_id':invoice['id'],'amount':'300'}])
    def test_expense_category_is_saved_per_company(self):
        payment={'direction':'expense','method':'cash','amount':'300','date':'1405/08/02','reason':'پرداخت اجاره','category':'اجاره'}
        self.s.finance_transaction(self.admin,'mana',payment)
        self.assertEqual(self.s.finance_list(self.admin,'mana')['transactions'][0]['category'],'اجاره')
        self.assertFalse(self.s.finance_list(self.admin,'arka')['transactions'])
    def test_receipt_is_scoped_and_integrity_checked(self):
        import base64
        tx=self.s.finance_transaction(self.admin,'mana',{'direction':'expense','method':'cash','amount':'300','date':'1405/08/02','reason':'اجاره'})
        data=base64.b64encode(b'test-receipt').decode('ascii');receipt=self.s.finance_receipt_add(self.admin,'mana',tx['id'],'../../رسید.pdf',data)
        self.assertEqual(self.s.finance_receipt_list(self.admin,'mana',tx['id'])[0]['name'],'رسید.pdf');self.assertEqual(self.s.finance_receipt_get(self.admin,'mana',receipt['id'])['data'],data)
        with self.assertRaises(DomainError):self.s.finance_receipt_get(self.admin,'arka',receipt['id'])
        with self.assertRaises(DomainError):self.s.finance_receipt_add(self.admin,'mana',tx['id'],'bad.exe',data)
        (self.s.files/(receipt['id']+'.bin')).write_bytes(b'tamper')
        with self.assertRaises(DomainError):self.s.finance_receipt_get(self.admin,'mana',receipt['id'])
    def test_server_backup_requires_each_financial_receipt(self):
        import base64
        from pathlib import Path
        from backup_bundle import create_bundle
        from server_restore import inspect_server_backup
        tx=self.s.finance_transaction(self.admin,'mana',{'direction':'expense','method':'cash','amount':'10','date':'1405/08/02','reason':'هزینه'})
        receipt=self.s.finance_receipt_add(self.admin,'mana',tx['id'],'receipt.pdf',base64.b64encode(b'receipt').decode())
        root=Path(self.tmp.name);db=root/'backup.sqlite';self.s.backup_database(db);path=root/'backup.karname';data={'events':[],'settings':{}}
        create_bundle(path,data,{'server/company.sqlite':db.read_bytes()})
        with self.assertRaises(ValueError):inspect_server_backup(path)
        path2=root/'complete.karname';create_bundle(path2,data,{'server/company.sqlite':db.read_bytes(),'server/files/'+receipt['id']+'.bin':b'receipt'});inspect_server_backup(path2)
    def test_bank_matching_requires_exact_amount_and_can_be_reversed(self):
        bank=self.s.finance_bank_add(self.admin,'mana','حساب','123')['id'];payment={'direction':'income','method':'paya','bank_id':bank,'amount':'300','date':'1405/08/02','reason':'واریز'}
        tx=self.s.finance_transaction(self.admin,'mana',payment)
        args=dict(company='mana',bank_id=bank,external_ref='0012',transaction_id=tx['id'],date='1405/08/02',value='300',direction='income')
        with self.assertRaises(DomainError):self.s.finance_match_bank(self.admin,**dict(args,value='301'))
        match=self.s.finance_match_bank(self.admin,**args)
        with self.assertRaises(DomainError):self.s.finance_match_bank(self.admin,**args)
        row=self.s.finance_list(self.admin,'mana')['transactions'][0]
        with self.assertRaises(DomainError):self.s.finance_transaction(self.admin,'mana',payment,id=tx['id'],version=row['version'])
        with self.assertRaises(DomainError):self.s.finance_unmatch_bank(self.admin,'arka',match['id'])
        self.s.finance_unmatch_bank(self.admin,'mana',match['id']);self.s.finance_transaction(self.admin,'mana',payment,id=tx['id'],version=row['version'])
    def test_sale_conversion_keeps_valid_quote_reference(self):
        basic={'title':'فاکتور','client_id':self.buyer['id'],'number':'__AUTO__','date':'1405/08/01','status':'draft','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}]}
        quote=self.s.save_record(self.admin,'invoice',dict(basic,document_type='پیش‌فاکتور'),'mana')
        sale=self.s.save_record(self.admin,'invoice',dict(basic,document_type='فاکتور فروش',source_quote_id=quote['id'],source_quote_number='جعلی'),'mana')
        self.assertEqual(sale['payload']['source_quote_number'],quote['payload']['number'])
        edited=dict(sale['payload'],source_quote_id='wrong');saved=self.s.save_record(self.admin,'invoice',edited,'mana',id=sale['id'],version=sale['version']);self.assertEqual(saved['payload']['source_quote_id'],quote['id'])
        other=self.s.save_record(self.admin,'client',{'title':'مشتری دیگر'},'mana')
        with self.assertRaises(DomainError):self.s.save_record(self.admin,'invoice',dict(basic,client_id=other['id'],document_type='فاکتور فروش',source_quote_id=quote['id']),'mana')
    def test_check_clearance_and_return_update_invoice_and_balance(self):
        check=self.s.finance_check_add(self.admin,'mana','334','بانک','600','1405/08/10')['id'];invoice=self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        row=self.s.finance_list(self.admin,'mana')['checks'][0];self.s.finance_check_status(self.admin,'mana',check,row['version'],'cleared')
        self.assertEqual(self.s.record(invoice['id'])['payload']['settlement_summary']['uncollected'],'400')
        self.assertEqual(self.s.finance_list(self.admin,'mana')['balances'][self.buyer['id']],'400')
        row=self.s.finance_list(self.admin,'mana')['checks'][0];self.s.finance_check_status(self.admin,'mana',check,row['version'],'returned')
        self.assertEqual(self.s.record(invoice['id'])['payload']['settlement_summary']['uncollected'],'1000')
    def test_deposited_check_is_not_counted_as_cleared(self):
        check=self.s.finance_check_add(self.admin,'mana','337','بانک','600','1405/08/10')['id'];invoice=self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        row=self.s.finance_list(self.admin,'mana')['checks'][0];self.s.finance_check_status(self.admin,'mana',check,row['version'],'deposited')
        summary=self.s.record(invoice['id'])['payload']['settlement_summary'];self.assertEqual(summary['pending_checks'],'600');self.assertEqual(summary['received'],'0');self.assertEqual(summary['uncollected'],'1000')
        history=self.s.finance_check_history(self.admin,'mana',check);self.assertEqual(history[0]['before']['status'],'pending');self.assertEqual(history[0]['after']['status'],'deposited')
        with self.assertRaises(DomainError):self.s.finance_check_history(self.admin,'arka',check)
    def test_check_alerts_obey_company_permissions_and_hide_closed_checks(self):
        user_id=self.s.save_user(self.admin,{'username':'staff','password':'test','fullname':'کارمند','memberships':[{'company_id':'mana','role':'employee'}]})['id'];staff=self.s.user(user_id)
        first=self.s.finance_check_add(self.admin,'mana','501','بانک','10','1405/08/10')['id'];second=self.s.finance_check_add(self.admin,'mana','502','بانک','20','1405/08/11')['id'];row=next(c for c in self.s.finance_list(self.admin,'mana')['checks'] if c['id']==second);self.s.finance_check_status(self.admin,'mana',second,row['version'],'cleared')
        with self.assertRaises(DomainError):self.s.finance_check_alerts(staff,'mana')
        self.s.save_permissions(self.admin,user_id,'mana',{'module.clients.view':True,'module.finance.view':True});staff=self.s.user(user_id);alerts=self.s.finance_check_alerts(staff,'mana');self.assertEqual([a['id'] for a in alerts],[first]);self.assertNotIn('amount',alerts[0])
        with self.assertRaises(DomainError):self.s.finance_check_alerts(staff,'arka')
    def test_finance_and_customer_edit_permissions_are_separate(self):
        uid=self.s.save_user(self.admin,{'username':'limited','password':'test','fullname':'همکار','memberships':[{'company_id':'mana','role':'employee'}]})['id']
        self.s.save_permissions(self.admin,uid,'mana',{'module.clients.view':True,'module.clients.edit':True,'module.finance.view':False});actor=self.s.user(uid)
        with self.assertRaises(DomainError):self.s.finance_list(actor,'mana')
        self.s.save_permissions(self.admin,uid,'mana',{'module.clients.view':True,'module.clients.edit':False,'module.finance.view':True,'module.finance.edit':True});actor=self.s.user(uid);self.s.finance_bank_add(actor,'mana','حساب')
        with self.assertRaises(DomainError):self.s.save_record(actor,'client',dict(self.buyer['payload'],title='تغییر'),'mana',id=self.buyer['id'],version=self.buyer['version'])
    def test_finance_acl_upgrade_preserves_existing_explicit_client_permissions(self):
        uid=self.s.save_user(self.admin,{'username':'legacy','password':'test','fullname':'قدیمی','memberships':[{'company_id':'mana','role':'employee'}]})['id']
        self.s.save_permissions(self.admin,uid,'mana',{'module.clients.view':True,'module.clients.edit':True})
        with self.s.db(True) as c:c.execute("DELETE FROM meta WHERE key='finance_acl_v1'")
        self.s=Store(self.tmp.name);actor=self.s.user(uid);self.s.finance_list(actor,'mana');self.s.finance_bank_add(actor,'mana','حساب قدیمی')
    def test_endorsed_check_tracks_source_and_purchase_without_double_counting(self):
        supplier=self.s.save_record(self.admin,'client',{'title':'فروشنده'},'mana')
        check=self.s.finance_check_add(self.admin,'mana','900','بانک','600','1405/08/10')['id'];source=self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        purchase=self.s.save_record(self.admin,'invoice',{'title':'خرید','client_id':supplier['id'],'number':'2','date':'1405/08/01','document_type':'فاکتور خرید','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]},'mana')
        row=self.s.finance_list(self.admin,'mana')['checks'][0];transfer=self.s.finance_transfer_check(self.admin,'mana',check,row['version'],supplier['id'],purchase['id'])
        listing=self.s.finance_list(self.admin,'mana');self.assertEqual(listing['balances'][self.buyer['id']],'1000');self.assertEqual(listing['balances'][supplier['id']],'-1000');dest=next(x for x in listing['invoice_documents'] if x['id']==purchase['id']);self.assertEqual(dest['allocated_pending_checks'],'600')
        with self.assertRaises(DomainError):self.s.finance_transaction(self.admin,'mana',{'direction':'expense','method':'cash','amount':'401','date':'1405/08/02','reason':'پرداخت','customer_id':supplier['id'],'invoice_id':purchase['id']})
        with self.assertRaises(DomainError):self.s.delete_record(self.admin,source['id'],source['version'])
        self.s.finance_check_status(self.admin,'mana',check,transfer['version'],'cleared');listing=self.s.finance_list(self.admin,'mana');self.assertEqual(listing['balances'][self.buyer['id']],'400');self.assertEqual(listing['balances'][supplier['id']],'-400');dest=next(x for x in listing['invoice_documents'] if x['id']==purchase['id']);self.assertEqual(dest['remaining_after_allocations'],'400')
        row=listing['checks'][0];self.s.finance_check_status(self.admin,'mana',check,row['version'],'returned');listing=self.s.finance_list(self.admin,'mana');self.assertEqual(listing['balances'][self.buyer['id']],'1000');self.assertEqual(listing['balances'][supplier['id']],'-1000')
    def test_transfer_reversal_requires_fresh_version_and_pending_check(self):
        supplier=self.s.save_record(self.admin,'client',{'title':'فروشنده'},'mana');check=self.s.finance_check_add(self.admin,'mana','901','بانک','600','1405/08/10')['id'];row=self.s.finance_list(self.admin,'mana')['checks'][0]
        transfer=self.s.finance_transfer_check(self.admin,'mana',check,row['version'],supplier['id'])
        with self.assertRaises(DomainError):self.s.finance_untransfer_check(self.admin,'mana',transfer['id'],row['version'])
        self.s.finance_untransfer_check(self.admin,'mana',transfer['id'],transfer['version']);self.assertFalse(self.s.finance_list(self.admin,'mana')['check_transfers'])
        self.assertEqual(self.s.finance_check_history(self.admin,'mana',check)[0]['action'],'check_untransfer')
    def test_transfer_and_cash_race_cannot_overallocate_purchase(self):
        from concurrent.futures import ThreadPoolExecutor
        supplier=self.s.save_record(self.admin,'client',{'title':'فروشنده'},'mana');check=self.s.finance_check_add(self.admin,'mana','902','بانک','600','1405/08/10')['id'];row=self.s.finance_list(self.admin,'mana')['checks'][0]
        purchase=self.s.save_record(self.admin,'invoice',{'title':'خرید','client_id':supplier['id'],'number':'2','date':'1405/08/01','document_type':'فاکتور خرید','status':'issued','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[]},'mana')
        def run(kind):
            try:
                if kind=='check':self.s.finance_transfer_check(self.admin,'mana',check,row['version'],supplier['id'],purchase['id'])
                else:self.s.finance_transaction(self.admin,'mana',{'direction':'expense','method':'cash','amount':'600','date':'1405/08/02','reason':'پرداخت','customer_id':supplier['id'],'invoice_id':purchase['id']})
                return True
            except DomainError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(run,['check','cash']))
        self.assertEqual(sorted(outcomes),[False,True])
    def test_linked_check_cannot_be_edited_with_stale_version(self):
        check=self.s.finance_check_add(self.admin,'mana','335','بانک','600','1405/08/10')['id'];old=self.s.finance_list(self.admin,'mana')['checks'][0]
        self.s.save_record(self.admin,'invoice',self.invoice('1',check),'mana')
        with self.assertRaises(DomainError):self.s.finance_check_edit(self.admin,'mana',check,old['version'],'335','بانک','700','1405/08/10')
        current=self.s.finance_list(self.admin,'mana')['checks'][0]
        with self.assertRaises(DomainError):self.s.finance_check_edit(self.admin,'mana',check,current['version'],'335','بانک','700','1405/08/10')
    def test_existing_check_schema_is_migrated(self):
        with self.s.db(True) as c:
            c.execute('DROP TABLE finance_check')
            c.execute("CREATE TABLE finance_check(id TEXT PRIMARY KEY,company_id TEXT NOT NULL,number TEXT NOT NULL,bank TEXT NOT NULL,amount TEXT NOT NULL,due_date TEXT NOT NULL,description TEXT NOT NULL,invoice_id TEXT,created TEXT NOT NULL)")
            c.execute("INSERT INTO finance_check VALUES('legacy','mana','10','بانک','600','1405/08/10','',NULL,'2026-10-01')")
        self.s=Store(self.tmp.name);row=self.s.finance_list(self.admin,'mana')['checks'][0]
        self.assertEqual((row['number'],row['status'],row['direction'],row['version']),('10','pending','received',1))
    def test_concurrent_invoice_numbers_do_not_collide(self):
        from concurrent.futures import ThreadPoolExecutor
        def save(_):
            store=Store(self.tmp.name)
            p={'title':'فاکتور','client_id':self.buyer['id'],'number':'__AUTO__','date':'1405/08/01','document_type':'فاکتور فروش','status':'draft','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}]}
            return store.save_record(self.admin,'invoice',p,'mana')['payload']
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(save,range(4)))
        self.assertEqual({r['number'] for r in rows},{'100','101','102','103'});self.assertEqual({r['document_no'] for r in rows},{'100','101','102','103'})

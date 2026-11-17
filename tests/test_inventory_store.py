import tempfile,unittest
from org_store import Store,DomainError

class InventoryStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(self.tmp.name);self.admin=self.s.bootstrap('admin','password','مدیر')
    def tearDown(self):self.tmp.cleanup()
    def test_trash_purge_preserves_products_with_financial_history(self):
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id'];group=self.s.inventory_group(self.admin,'mana','فرعی',root)['id'];item=self.s.inventory_product(self.admin,'mana',{'group_id':group,'name':'کالا','code':'01'})['id'];buyer=self.s.save_record(self.admin,'client',{'title':'مشتری'},'mana')
        self.s.save_record(self.admin,'invoice',dict(client_id=buyer['id'],number='__AUTO__',date='1405/08/01',document_type='فاکتور فروش',status='draft',lines=[dict(description='کالا',product_id=item,quantity='1',unit_price='100')]),'mana');self.s.inventory_archive(self.admin,'mana',item,1)
        with self.assertRaises(DomainError):self.s.workspace_trash(self.admin,kind='product',id=item,version=2,purge=True)
        self.s.workspace_trash(self.admin,kind='product',id=item,version=2,restore=True);self.assertTrue(self.s.inventory_list(self.admin,'mana')['products'][0]['active'])
    def test_empty_archived_custom_group_can_be_purged(self):
        scope='__shared_chat__';room=self.s.workspace_group_create(self.admin,scope,'گروه آزمایشی',[])['room'];self.s.workspace_hide_room(self.admin,scope,room);self.s.workspace_trash(self.admin,kind='group',id=room,company=scope,purge=True)
        with self.s.db() as c:self.assertIsNone(c.execute('SELECT 1 FROM workspace_groups WHERE company_id=? AND room=?',(scope,room)).fetchone())
    def test_groups_stock_adjust_and_stale_update(self):
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id'];child=self.s.inventory_group(self.admin,'mana','فرعی',root)['id']
        with self.assertRaises(DomainError):self.s.inventory_group(self.admin,'mana','تکراری',child)
        item=self.s.inventory_product(self.admin,'mana',{'group_id':child,'name':'کالا','code':'01','purchase_price':'1250000','sale_price':'1500000'})['id']
        self.assertEqual(self.s.inventory_adjust(self.admin,'mana',item,1,'-2.5','اصلاح شمارش')['balance'],'-2.5')
        with self.assertRaises(DomainError):self.s.inventory_adjust(self.admin,'mana',item,1,'5','اصلاح دوباره')
        result=self.s.inventory_list(self.admin,'mana');self.assertEqual(result['products'][0]['balance'],'-2.5');self.assertEqual(len(result['groups']),2)
        with self.s.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM stock_movements').fetchone()[0],1)
    def test_company_isolation(self):
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id']
        with self.assertRaises(DomainError):self.s.inventory_group(self.admin,'arka','فرعی',root)
        self.assertEqual(self.s.inventory_list(self.admin,'arka')['groups'],[])
    def test_discounted_invoice_recomputes_margin_on_server(self):
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id'];group=self.s.inventory_group(self.admin,'mana','فرعی',root)['id'];item=self.s.inventory_product(self.admin,'mana',{'group_id':group,'name':'کالا','code':'01','purchase_price':'600','sale_price':'1000'})['id'];buyer=self.s.save_record(self.admin,'client',{'title':'مشتری'},'mana')
        payload={'title':'فاکتور','client_id':buyer['id'],'number':'__AUTO__','date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'کالا','product_id':item,'quantity':'1','unit_price':'1000','discount':'0','discount_rate':'10','tax_rate':'10'}],'invoice_discount_mode':'percent','invoice_discount_value':'10','additional_charge':'50','charge_tax_rate':'20'}
        saved=self.s.save_record(self.admin,'invoice',payload,'mana');self.assertEqual(saved['payload']['totals']['total'],'951');self.assertEqual(saved['payload']['lines'][0]['gross_profit'],'210');self.assertEqual(saved['payload']['settlement_summary']['uncollected'],'951')
    def test_invoice_stock_is_atomic_and_reversible(self):
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id'];group=self.s.inventory_group(self.admin,'mana','فرعی',root)['id']
        item=self.s.inventory_product(self.admin,'mana',{'group_id':group,'name':'کالا','code':'01','purchase_price':'100','sale_price':'200'})['id']
        buyer=self.s.save_record(self.admin,'client',{'title':'مشتری'},'mana')
        payload={'title':'فاکتور','client_id':buyer['id'],'number':'001','date':'1405/08/01','document_type':'فاکتور فروش','status':'issued','lines':[{'description':'کالا','product_id':item,'quantity':'2','unit_price':'200'}]}
        record=self.s.save_record(self.admin,'invoice',payload,'mana')
        def balance():return self.s.inventory_list(self.admin,'mana')['products'][0]['balance']
        self.assertEqual(balance(),'-2')
        record=self.s.save_record(self.admin,'invoice',record['payload'],'mana',id=record['id'],version=record['version']);self.assertEqual(balance(),'-2')
        self.s.delete_record(self.admin,record['id'],record['version']);self.assertEqual(balance(),'0')
        self.s.workspace_trash(self.admin,kind='record',id=record['id'],version=record['version']+1,restore=True);self.assertEqual(balance(),'-2')
    def test_server_backup_contains_stock_and_bank(self):
        from pathlib import Path
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id'];group=self.s.inventory_group(self.admin,'mana','فرعی',root)['id']
        item=self.s.inventory_product(self.admin,'mana',{'group_id':group,'name':'کالا','code':'01'})['id'];self.s.inventory_adjust(self.admin,'mana',item,1,'-3','شمارش')
        self.s.finance_bank_add(self.admin,'mana','حساب نمونه','123')
        self.s.finance_transaction(self.admin,'mana',{'direction':'income','method':'cash','amount':'10','date':'1405/08/01','reason':'آزمایش'})
        self.s.finance_check_add(self.admin,'mana','444','بانک','50','1405/08/10',direction='issued')
        copy=Path(self.tmp.name)/'backup.sqlite';self.s.backup_database(copy)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(copy)) as c:
            self.assertEqual(c.execute('SELECT balance FROM stock_products').fetchone()[0],'-3')
            self.assertEqual(c.execute('SELECT name FROM finance_bank').fetchone()[0],'حساب نمونه')
            self.assertEqual(c.execute('SELECT reason FROM finance_transactions').fetchone()[0],'آزمایش')
            self.assertEqual(c.execute('SELECT direction FROM finance_check').fetchone()[0],'issued')
    def test_auto_codes_are_sequential_and_not_reused(self):
        from concurrent.futures import ThreadPoolExecutor
        root=self.s.inventory_group(self.admin,'mana','اصلی')['id'];sub=self.s.inventory_group(self.admin,'mana','فرعی',root)['id']
        def add(i):
            store=Store(self.tmp.name)
            return store.inventory_product(self.admin,'mana',{'group_id':sub,'name':'کالا '+str(i),'code':'__AUTO__'})
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(add,range(4)))
        self.assertEqual({x['code'] for x in rows},{'1000','1001','1002','1003'})
        first=next(x for x in rows if x['code']=='1000');self.s.inventory_archive(self.admin,'mana',first['id'],1)
        self.assertEqual(add(5)['code'],'1004')

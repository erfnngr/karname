import tempfile,unittest
from org_http import RunningServer
from org_client import Client

class InvoiceNetworkTest(unittest.TestCase):
    def test_invoice_responses_do_not_expose_finance_details_without_finance_view(self):
        with tempfile.TemporaryDirectory() as folder:
            server=RunningServer(folder,'127.0.0.1',0,background=False);admin=server.store.bootstrap('admin','password','مدیر');user=server.store.save_user(admin,{'username':'staff','password':'password','fullname':'همکار','memberships':[{'company_id':'mana','role':'finance'}]})['id'];server.store.save_permissions(admin,user,'mana',{'module.finance.view':False})
            a=Client('http://127.0.0.1:'+str(server.port));b=Client('http://127.0.0.1:'+str(server.port))
            try:
                a.login('admin','password');b.login('staff','password');buyer=a.request('records',{'kind':'client','company':'mana','payload':{'title':'مشتری'}})['id'];bank=a.request('finance/bank',{'company':'mana','name':'بانک','account_no':'987654321','iban':'IR123'})['id']
                invoice=a.request('records',{'kind':'invoice','company':'mana','payload':{'title':'فروش','client_id':buyer,'number':'101','date':'1405/08/01','status':'issued','document_type':'فاکتور فروش','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000'}],'settlement':[{'kind':'bank','bank_account_id':bank,'amount':'200'}]}})
                result=b.request('record',id=invoice['id'])['payload'];self.assertNotIn('settlement',result);self.assertNotIn('settlement_summary',result);self.assertNotIn('account_no',result['seller_snapshot']);self.assertEqual(result['totals']['total'],'1000')
                delta=b.request('workspace/records-delta',{'after':0,'known':[]});item=next(r for r in delta['items'] if r['id']==invoice['id']);self.assertNotIn('settlement',item['payload'])
                self.assertEqual(b.request('records',kind='invoice',company='mana',q='987654321')['total'],0)
                history=b.request('history',id=invoice['id']);self.assertTrue(history);self.assertIsNone(history[0]['after_json'])
                export=b.request('export',company='mana')['data'];self.assertNotIn('mana',export['finance']);item=next(r for r in export['records'] if r['id']==invoice['id']);self.assertNotIn('settlement',item['payload'])
            finally:a.session.close();b.session.close();server.close()
    def test_two_clients_see_the_same_stock(self):
        with tempfile.TemporaryDirectory() as folder:
            server=RunningServer(folder,'127.0.0.1',0,background=False);server.store.bootstrap('admin','password','مدیر')
            a=Client('http://127.0.0.1:'+str(server.port));b=Client('http://127.0.0.1:'+str(server.port))
            try:
                a.login('admin','password');b.login('admin','password')
                group=a.request('inventory/group',{'company':'mana','name':'اصلی'})['id'];sub=a.request('inventory/group',{'company':'mana','name':'فرعی','parent_id':group})['id']
                product=a.request('inventory/product',{'company':'mana','payload':{'name':'کالا','code':'123','group_id':sub,'purchase_price':'90','sale_price':'100'}})['id']
                buyer=a.request('records',{'kind':'client','company':'mana','payload':{'title':'مشتری'}})['id']
                a.request('records',{'kind':'invoice','company':'mana','payload':{'title':'فاکتور','client_id':buyer,'number':'123','date':'1405/08/01','status':'issued','document_type':'فاکتور فروش','lines':[{'description':'کالا','product_id':product,'quantity':'3','unit_price':'100'}]}})
                item=b.request('inventory',company='mana')['products'][0];self.assertEqual(item['balance'],'-3')
                a.request('inventory/adjust',{'company':'mana','id':product,'version':item['version'],'balance':'10','reason':'شمارش'})
                self.assertEqual(b.request('inventory',company='mana')['products'][0]['balance'],'10')
                tx=a.request('finance/transaction',{'company':'mana','payload':{'direction':'income','method':'cash','amount':'20','date':'1405/08/02','reason':'دریافت','customer_id':buyer}})
                self.assertEqual(b.request('finance',company='mana')['transactions'][0]['document_no'],tx['document_no'])
                check=a.request('finance/check',{'company':'mana','number':'99','bank':'بانک','value':'30','due_date':'1405/08/10','direction':'received'})
                row=b.request('finance',company='mana')['checks'][0];self.assertEqual(row['document_no'],check['document_no'])
                b.request('finance/check/status',{'company':'mana','id':check['id'],'version':row['version'],'status':'cleared'});self.assertEqual(a.request('finance',company='mana')['checks'][0]['status'],'cleared')
                bank=a.request('finance/bank',{'company':'mana','name':'حساب'})['id'];payment=a.request('finance/transaction',{'company':'mana','payload':{'direction':'income','method':'paya','bank_id':bank,'amount':'50','date':'1405/08/02','reason':'واریز'}})
                match=b.request('finance/bank-match',{'company':'mana','bank_id':bank,'external_ref':'12345','transaction_id':payment['id'],'date':'1405/08/02','value':'50','direction':'income'})
                self.assertEqual(a.request('finance',company='mana')['bank_matches'][0]['id'],match['id']);a.request('finance/bank-unmatch',{'company':'mana','id':match['id']});self.assertFalse(b.request('finance',company='mana')['bank_matches'])
                import base64
                receipt=a.request('finance/receipt',{'company':'mana','transaction_id':payment['id'],'name':'receipt.pdf','data':base64.b64encode(b'receipt').decode()})
                self.assertEqual(b.request('finance/receipts',company='mana',transaction_id=payment['id'])[0]['id'],receipt['id']);self.assertEqual(base64.b64decode(b.request('finance/receipt',company='mana',id=receipt['id'])['data']),b'receipt')
                check2=a.request('finance/check',{'company':'mana','number':'100','bank':'بانک','value':'30','due_date':'1405/08/10','direction':'received'});state=next(c for c in b.request('finance',company='mana')['checks'] if c['id']==check2['id'])
                transfer=b.request('finance/check-transfer',{'company':'mana','check_id':check2['id'],'version':state['version'],'recipient_id':buyer});self.assertEqual(a.request('finance',company='mana')['check_transfers'][0]['id'],transfer['id'])
                a.request('finance/check-untransfer',{'company':'mana','id':transfer['id'],'version':transfer['version']});self.assertFalse(b.request('finance',company='mana')['check_transfers'])
                alerts=b.request('finance/check-alerts',company='mana');self.assertEqual([x['id'] for x in alerts],[check2['id']]);self.assertNotIn('amount',alerts[0])
            finally:a.session.close();b.session.close();server.close()

import unittest
from finance_ledger import statement


class StatementTest(unittest.TestCase):
    def test_statement_includes_invoice_and_payments_once(self):
        invoices=[{'payload':{'client_id':'a','document_type':'فاکتور فروش','status':'issued','date':'1405/01/01','number':'100','document_no':'101','totals':{'total':'1000'},'settlement':[{'kind':'cash','amount':'200'}],'settlement_summary':{'received':'200'}}}]
        tx=[{'customer_id':'a','date':'1405/01/02','document_no':'102','amount':'300','direction':'income','reason':'پرداخت','source':'transaction'}]
        rows,incomplete=statement('a',invoices,tx)
        self.assertEqual([r['balance'] for r in rows],['1000','800','500']);self.assertFalse(incomplete)
        invoices[0]['payload'].pop('settlement_summary');self.assertTrue(statement('a',invoices,tx)[1])
    def test_only_cleared_endorsed_check_changes_recipient_balance(self):
        invoice={'payload':{'client_id':'a','document_type':'فاکتور خرید','status':'issued','date':'1405/01/01','number':'1','document_no':'100','totals':{'total':'1000'},'settlement_summary':{'received':'0'}}}
        check={'recipient_id':'a','status':'pending','amount':'600','number':'55','cleared_date':'1405/01/15'}
        self.assertEqual(statement('a',[invoice],[],[check])[0][-1]['balance'],'-1000')
        check['status']='cleared';rows,_=statement('a',[invoice],[],[check]);self.assertEqual(rows[-1]['balance'],'-400');self.assertEqual(rows[-1]['date'],'1405/01/15')
    def test_cleared_check_uses_clearance_date_not_invoice_date(self):
        invoice={'payload':{'client_id':'a','document_type':'فاکتور فروش','status':'issued','date':'1405/01/01','number':'1','document_no':'100','totals':{'total':'1000'},'settlement':[{'kind':'check','check_id':'c','amount':'600'}],'settlement_summary':{'received':'600'}}}
        check={'id':'c','number':'55','status':'cleared','cleared_date':'1405/01/15'}
        rows,incomplete=statement('a',[invoice],[],checks=[check]);self.assertFalse(incomplete);self.assertEqual(rows[-1]['date'],'1405/01/15');self.assertEqual(rows[-1]['balance'],'400')
        check['cleared_date']='';rows,incomplete=statement('a',[invoice],[],checks=[check]);self.assertTrue(incomplete);self.assertEqual(rows[-1]['date'],'نامشخص')

import unittest
from decimal import Decimal
from inventory_logic import stock_changes,gross_profit,invoice_quantities

def sale(q='2',status='issued',kind='فاکتور فروش',product='a'):
    return {'document_type':kind,'status':status,'lines':[{'product_id':product,'quantity':q}]}

class InventoryLogicTest(unittest.TestCase):
    def test_issue_edit_delete_restore(self):
        self.assertEqual(stock_changes(None,sale()),{'a':Decimal('-2')})
        self.assertEqual(stock_changes(sale(),sale('3.5')),{'a':Decimal('-1.5')})
        self.assertEqual(stock_changes(sale(),sale(),after_deleted=True),{'a':Decimal('2')})
        self.assertEqual(stock_changes(sale(),sale(),before_deleted=True),{'a':Decimal('-2')})
        self.assertEqual(stock_changes(sale(),sale()),{})
    def test_drafts_preinvoices_and_cancellations(self):
        self.assertEqual(invoice_quantities(sale(status='draft')),{})
        self.assertEqual(invoice_quantities(sale(kind='پیش‌فاکتور')),{})
        self.assertEqual(stock_changes(sale(),sale(status='cancelled')) ,{'a':Decimal('2')})
        self.assertEqual(stock_changes(None,sale('3',kind='فاکتور خرید')) ,{'a':Decimal('3')})
        self.assertEqual(stock_changes(None,sale('3',kind='برگشت از فروش')) ,{'a':Decimal('3')})
        self.assertEqual(stock_changes(None,sale('3',kind='برگشت از خرید')) ,{'a':Decimal('-3')})
    def test_duplicate_lines_and_replacement(self):
        value=sale();value['lines'].append({'product_id':'a','quantity':'1.25'})
        self.assertEqual(invoice_quantities(value),{'a':Decimal('3.25')})
        self.assertEqual(stock_changes(sale(),sale('4',product='b')),{'a':Decimal('2'),'b':Decimal('-4')})
    def test_estimate_and_invalid(self):
        self.assertEqual(gross_profit('2','100','60','10'),Decimal('70'))
        for value in ('-1','NaN','Infinity'):
            with self.assertRaises(ValueError):invoice_quantities(sale(value))

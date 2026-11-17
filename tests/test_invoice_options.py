import unittest
from invoice_pdf import sample_document,with_allocated_payments


class InvoiceOptionsTest(unittest.TestCase):
    def test_print_options_escape_footer_and_hide_only_optional_fields(self):
        p={'title':'فاکتور','number':'100','client_id':'x','date':'1405/01/01','document_type':'فاکتور فروش','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}],'seller_name':'مانا','seller_snapshot':{'account_no':'123','iban':'IR123'}}
        html=sample_document(p,{'show_logo':False,'show_bank':False,'footer':'سپاس <test>'})
        self.assertNotIn('karname-company-logo',html);self.assertNotIn('IR123',html);self.assertIn('سپاس &lt;test&gt;',html);self.assertIn('جمع کل',html)
        self.assertIn('IR123',sample_document(p))
    def test_allocations_are_in_print_snapshot_not_stored_payload(self):
        payload={'settlement_summary':{'received':'100','uncollected':'900'}}
        view=with_allocated_payments(payload,'300');self.assertEqual(view['settlement_summary']['received'],'400');self.assertEqual(view['settlement_summary']['uncollected'],'600');self.assertEqual(payload['settlement_summary']['received'],'100')
    def test_print_shows_charge_and_discounted_line_amounts(self):
        p={'title':'فاکتور','number':'100','date':'1405/01/01','document_type':'فاکتور فروش','lines':[{'description':'خدمت','quantity':'1','unit_price':'1000','discount':'0','discount_rate':'10','tax_rate':'10'}],'invoice_discount_mode':'percent','invoice_discount_value':'10','additional_charge':'50','charge_tax_rate':'20'}
        html=sample_document(p);self.assertIn('هزینه اضافی',html);self.assertIn('مالیات هزینه',html);self.assertIn('۹۵۱',html);self.assertIn('۱۹۰',html)
    def test_custom_sections_and_sizes_are_honored(self):
        p={'title':'فاکتور','number':'100','date':'1405/01/01','document_type':'فاکتور فروش','notes':'یادداشت خاص','lines':[{'description':'خدمت','quantity':'1','unit_price':'100'}]}
        html=sample_document(p,{'show_seller':False,'show_buyer':False,'show_signature':False,'show_notes':False,'font_size':10,'cell_padding':6,'blank_rows':1})
        self.assertNotIn('مشخصات فروشنده',html);self.assertNotIn('مشخصات خریدار',html);self.assertNotIn('مهر و امضا',html);self.assertNotIn('یادداشت خاص',html);self.assertIn('font-size:10pt',html);self.assertIn('padding:6px',html);self.assertIn('جمع کل',html)

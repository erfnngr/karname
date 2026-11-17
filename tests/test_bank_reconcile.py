import tempfile
import unittest
from pathlib import Path
from bank_reconcile import read_rows,suggestions


class BankReconcileTests(unittest.TestCase):
    def test_exact_suggestions_never_mutate_and_filter_bank(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bank.csv';path.write_text('تاریخ,مبلغ,نوع,شرح\n۱۴۰۵/۱/۱,"۱,۰۰۰",واریز,آزمایش\n',encoding='utf-8-sig')
            rows=read_rows(path);tx=[dict(id='a',document_no='100',bank_id='b',amount='1000',date='1405/01/01',direction='income'),dict(id='c',document_no='101',bank_id='other',amount='1000',date='1405/01/01',direction='income')]
            self.assertEqual(suggestions(rows,tx,'b')[0]['matches'],[{'id':'a','document_no':'100'}]);self.assertEqual(len(tx),2)
    def test_invalid_date_fails_with_row_number(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bank.csv';path.write_text('تاریخ,مبلغ,نوع\nbad,10,برداشت\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'ردیف 2'):read_rows(path)
    def test_separate_credit_debit_and_manual_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bank.csv';path.write_text('روز,واریزی,برداشتی,رهگیری\n۱۴۰۵/۰۱/۰۱,۱۰۰۰,۰,123\n۱۴۰۵/۰۱/۰۲,۰,۵۰۰,124\n',encoding='utf-8-sig')
            rows=read_rows(path,{'date':0,'income':1,'expense':2,'reference':3,'amount':None,'direction':None})
            self.assertEqual([(r['direction'],r['amount']) for r in rows],[('income','1000'),('expense','500')])
            path.write_text('روز,واریزی,برداشتی\n۱۴۰۵/۰۱/۰۱,۱۰۰,۲۰۰\n',encoding='utf-8-sig')
            with self.assertRaisesRegex(ValueError,'ردیف 2'):read_rows(path,{'date':0,'income':1,'expense':2})
    def test_xlsx_headers_and_no_cross_bank_suggestions(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bank.xlsx';book=Workbook();sheet=book.active;sheet.append(['تاریخ','واریز','برداشت','شماره پیگیری']);sheet.append(['1405/01/01',100,0,'ref-1']);book.save(path);book.close()
            rows=read_rows(path);self.assertEqual(rows[0]['reference'],'ref-1')
            tx=[dict(id='x',document_no='1',bank_id='other',amount='100',date='1405/01/01',direction='income')]
            self.assertEqual(suggestions(rows,tx,'bank')[0]['matches'],[])

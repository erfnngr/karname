import tempfile,unittest
from pathlib import Path
from openpyxl import load_workbook
from insurance_reports import draft_report,tracking_report
from org_reports import spreadsheet

class InsuranceReportTests(unittest.TestCase):
    def test_draft_report_includes_omitted_person_for_review(self):
        draft=dict(title='test',workshop_id='w',period='1405/08',list_no='1',rows=[])
        profiles={'p':{'workshop_id':'w','employee_id':'e','start_date':'1405/01/01'}}
        rows=draft_report(draft,{'title':'کارگاه','workshop_code':'1'},profiles,{'e':{}},{'p':'همکار'})
        self.assertTrue(any(r['کارمند']=='همکار' and 'در لیست نیست' in r['موارد بررسی'] for r in rows))
    def test_tracking_separates_companies_and_never_claims_settlement(self):
        lists=[{'id':'l','company_id':'mana','title':'لیست','payload':{'workshop_id':'w','period':'1405/08','list_no':'1'}},
               {'id':'l2','company_id':'mana','title':'دیگر','payload':{'workshop_id':'w','period':'1405/09','list_no':'2'}}]
        def event(company,list_id,kind,amount=''):
            return {'kind':'insurance_evidence','company_id':company,'payload':{'insurance_list_id':list_id,'kind':kind,'amount':amount}}
        events=[event('mana','l','ارسال دستی'),event('mana','l','پرداخت دستی','100'),event('mana','l','پرداخت دستی','50'),event('arka','l','پرداخت دستی','999')]
        first,second=tracking_report(lists,{('mana','w'):'کارگاه'},events)
        self.assertEqual(first['جمع مبالغ رسید ثبت‌شده ریال'],'150');self.assertEqual(first['تعداد رسید پرداخت'],2)
        self.assertEqual(first['پیگیری ارسال دستی'],'ثبت شده');self.assertIn('تسویه کامل بررسی نشده',first['توضیح'])
        self.assertEqual(second['پیگیری ارسال دستی'],'ثبت نشده');self.assertEqual(second['پیگیری پرداخت دستی'],'ثبت نشده')
    def test_draft_report_is_labeled_and_excel_neutralizes_formulas(self):
        draft=dict(title='test',workshop_id='w',period='1405/08',list_no='1',rows=[dict(profile_id='p',days='30',daily_wage='',daily_seniority='0',insured_benefits='0',non_insured_benefits='0',unemployment_applies=True)])
        rows=draft_report(draft,{'title':'کارگاه','workshop_code':'1'},{'p':{'workshop_id':'w','employee_id':'e'}},{'e':{}},{'p':'=1+1'})
        self.assertIn('فایل ارسال نیست',rows[0]['نوع گزارش']);self.assertIn('مزد روزانه',rows[0]['موارد بررسی'])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'draft.xlsx';spreadsheet(path,rows);sheet=load_workbook(path).active
            self.assertEqual(sheet['F2'].value,"'=1+1")

import unittest
from decimal import Decimal
from tax_center import summarize_invoices
from permission_policy import baseline_allowed
from org_store import record_module,Store,DomainError

def invoice(company,kind,status,date='1405/02/10',tax='10'):
    return dict(company_id=company,kind='invoice',payload=dict(document_type=kind,status=status,date=date,totals=dict(subtotal='100',discount='10',tax=tax,total='100')))

class TaxCenterTests(unittest.TestCase):
    def test_fast_periods_respect_jalali_month_lengths(self):
        from tax_workflows import period_bounds
        self.assertEqual(period_bounds(1405,8,'quarter'),('1405/07/01','1405/09/30'))
        self.assertEqual(period_bounds(1405,1,'month'),('1405/01/01','1405/01/31'))
        self.assertEqual(period_bounds(1405,12,'year')[0],'1405/01/01')
    def test_comparison_is_scoped_by_company_date_and_status(self):
        records=[invoice('a','فاکتور فروش','issued'),invoice('a','برگشت از فروش','paid',tax='2'),invoice('b','فاکتور خرید','issued'),invoice('a','پیش‌فاکتور','draft'),invoice('a','فاکتور خرید','cancelled'),invoice('a','فاکتور خرید','issued','1405/03/02')]
        result=summarize_invoices(records,'a','1405/02/01','1405/02/31')
        self.assertEqual(result['sales']['count'],1);self.assertEqual(result['sales']['base'],Decimal(90));self.assertEqual(result['sales_return']['tax'],Decimal(2));self.assertEqual(result['purchase']['count'],0)
    def test_invalid_amount_is_excluded_and_reported(self):
        result=summarize_invoices([invoice('a','فاکتور فروش','issued',tax='bad')],'a','1405/01/01','1405/12/29')
        self.assertEqual(result['skipped'],1);self.assertEqual(result['sales']['count'],0)
    def test_scoped_permissions_and_validation(self):
        self.assertEqual(record_module('tax_case'),'tax');self.assertFalse(baseline_allowed('employee','tax','view'));self.assertTrue(baseline_allowed('finance','tax','create'))
        with self.assertRaises(ValueError):Store.validate(None,'tax_case',dict(title='ارزش افزوده',tax_type='ارزش افزوده',period='1405',status='draft',due_date='1405/13/01'))

import test_v6_ui as fixtures
class TaxIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.V6UiTests.setUpClass();cls.app=fixtures.V6UiTests.app
    setUp=fixtures.V6UiTests.setUp
    tearDown=fixtures.V6UiTests.tearDown
    pump=fixtures.V6UiTests.pump
    def test_workflow_and_fast_period_navigation(self):
        panel=self.win.tax_center;panel.workflow.setCurrentText('حقوق');panel.show_workflow_cases();self.assertEqual(panel.kind.currentText(),'حقوق');self.assertEqual(panel.tabs.currentIndex(),1)
        panel.set_period('quarter');self.assertTrue(panel.start.text());self.assertTrue(panel.end.text())
    def test_settings_search_includes_control_labels(self):
        from settings_ui import SettingsDialog
        dialog=SettingsDialog(self.win);dialog.category_search.setText('اندازه نوشته');self.app.processEvents()
        visible=[dialog.categories.item(i).text() for i in range(dialog.categories.count()) if not dialog.categories.item(i).isHidden()]
        self.assertIn('ظاهر',visible);dialog.close();dialog.deleteLater()
    def test_chat_message_can_create_calendar_reminder(self):
        from unittest.mock import patch,MagicMock
        from PySide6.QtWidgets import QDialog
        before=len(self.win.events);dialog=MagicMock();dialog.exec.return_value=QDialog.Accepted;dialog.payload=dict(company='شخصی',title='پیگیری پیام',date_jalali='1405/08/20',notes='متن پیام',priority='متوسط',recurrence='بدون تکرار',lead_days=[1,0],category='سایر',reminder_custom=True,reminder_group='personal')
        with patch('app.EventDialog',return_value=dialog):self.win.chat.remind({'id':'sample','text':'متن پیام'})
        self.assertEqual(len(self.win.events),before+1);self.assertEqual(self.win.events[-1]['source_chat_id'],'sample')
    def test_tax_record_sync_and_employee_cannot_read(self):
        payload=dict(title='ارزش افزوده بهار',tax_type='ارزش افزوده',period='1405/بهار',due_date='1405/04/31',status='draft',declared_amount='120',paid_amount='0',responsible='حسابدار',submitted_date='1405/04/20',payment_date='1405/04/21')
        record=self.client.request('records',dict(kind='tax_case',company='mana',payload=payload))
        self.assertEqual(record['payload']['responsible'],'حسابدار');self.assertEqual(record['payload']['submitted_date'],'1405/04/20')
        self.win.org.sync();self.pump(lambda:not self.win.org.busy);self.win.tabs.setCurrentWidget(self.win.tax_center);self.win.tax_center.company.setCurrentIndex(self.win.tax_center.company.findData('mana'));self.win.tax_center.render()
        self.assertEqual(self.win.tax_center.cases.rowCount(),1);self.assertEqual(self.win.tax_center.selected(),None)
        from org_client import Client
        staff=Client(self.client.url);staff.login('staff','ک')
        self.assertFalse(any(x['id']==record['id'] for x in staff.records(company='mana')))
        with self.assertRaises(Exception):staff.request('record',id=record['id'])
    def test_assistant_creates_idempotent_draft_and_rejects_implicit_due(self):
        from ai_app_actions import normalize_action
        from uuid import uuid4
        context=dict(actor=self.user,online=True,companies={'mana':{'id':'mana','name':'مانا'}},query='ثبت تکلیف ارزش افزوده برای شرکت مانا عنوان ارزش افزوده بهار دوره بهار 1405 موعد 1405/04/31')
        action=dict(type='tax_case_create',company_id='mana',changes=dict(title='ارزش افزوده بهار',tax_type='ارزش افزوده',period='بهار 1405',due_date='1405/04/31'))
        prepared=normalize_action(action,context);payload=dict(prepared['changes'],status='draft',assistant_request_id=prepared['request_id'])
        first=self.client.request('records',dict(kind='tax_case',company='mana',payload=payload));second=self.client.request('records',dict(kind='tax_case',company='mana',payload=payload))
        self.assertEqual(first['id'],second['id']);self.assertEqual(first['payload']['status'],'draft')
        context['query']='ثبت تکلیف برای شرکت مانا'
        with self.assertRaises(ValueError):normalize_action(action,context)
        context['query']='ویرایش پرونده ارزش افزوده بهار شرکت مانا مبلغ پرداختی 120 ریال';context['public']={'tax_cases':[dict(id=first['id'],version=first['version'],company_id='mana',company='مانا',title='ارزش افزوده بهار')]}
        update=normalize_action(dict(type='tax_case_update',target=first['id'],changes={'paid_amount':'120'}),context)
        self.assertEqual(update['changes']['paid_amount'],'120')
        context['query']='ویرایش پرونده ارزش افزوده بهار شرکت مانا'
        with self.assertRaises(ValueError):normalize_action(dict(type='tax_case_update',target=first['id'],changes={'paid_amount':'120'}),context)
        context['query']='مقایسه شرکت مانا از 1405/01/01 تا 1405/03/31'
        comparison=normalize_action(dict(type='tax_compare',company_id='mana',changes={'start':'1405/01/01','end':'1405/03/31'}),context)
        self.assertEqual(comparison['changes']['end'],'1405/03/31')

if __name__=='__main__':unittest.main()

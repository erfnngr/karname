"""Adapter between the tax roadmap presentation and existing tax workflows."""
import json
from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from tax_workflows import WORKFLOWS, workflow_progress, step_guide, case_review


class ReactTaxBridge(QObject):
    changed=Signal(str)
    completed=Signal(str,str)
    def __init__(self,panel,parent=None,show_native=None):
        super().__init__(parent);self.panel=panel;self.show_native=show_native;self.last='';self.timer=QTimer(self);self.timer.setInterval(1200);self.timer.timeout.connect(self._tick);self.timer.start()

    def _tick(self):
        from react_design_host import should_poll_section
        p = self.panel
        rv = getattr(p, 'react_view', None)
        if not should_poll_section(getattr(p, 'owner', None), rv if rv is not None else p):
            return
        self.publish()

    def publish(self):
        p=self.panel;allowed=p.company_permitted();category=p.workflow.currentText();case_id=p.map_case.currentData() if allowed else None
        record=next((r for r in p.owner.org.records if r.get('id')==case_id and r.get('company_id')==p.company.currentData()),None) if case_id else None
        steps=WORKFLOWS.get(category,());done=workflow_progress(record['payload']) if record else [False]*len(steps)
        detail=None
        if record:
            pl=record.get('payload',{})
            detail={'id':record['id'],'title':pl.get('title',''),'period':pl.get('period',''),'due_date':pl.get('due_date',''),'status':pl.get('status',''),'reference':pl.get('reference',''),'responsible':pl.get('responsible',''),'findings':case_review(pl)}
        can_edit=bool(allowed and p.company_permitted('edit'))
        can_create=bool(allowed and p.company_permitted('create'))
        state={'allowed':allowed,'can_edit':can_edit,'can_create':can_create,'company':p.company.currentText() if allowed else '', 'company_id':p.company.currentData() if allowed else None,
               'companies':[{'id':p.company.itemData(i),'label':p.company.itemText(i)} for i in range(p.company.count())], 'category':category,'categories':list(WORKFLOWS),
               'cases':[{'id':p.map_case.itemData(i),'label':p.map_case.itemText(i)} for i in range(1,p.map_case.count())] if allowed else [],
               'selected_case':case_id,'selected_case_detail':detail,
               'steps':[{'title':text,'description':step_guide(category,i),'done':bool(done[i])} for i,text in enumerate(steps)],
               'status':p.map_status.text() if allowed else ''}
        raw=json.dumps(state,ensure_ascii=False)
        if raw!=self.last:self.last=raw;self.changed.emit(raw)

    @Slot(str,str,str)
    def request(self,request_id,action,raw):
        try:
            if len(raw)>4000 or len(request_id)>80:raise ValueError('درخواست معتبر نیست.')
            data=json.loads(raw);p=self.panel
            if not isinstance(data,dict):raise ValueError('درخواست معتبر نیست.')
            value=None
            if action=='refresh' and not data:self.last=''
            elif action=='category' and set(data)=={'name'} and data['name'] in WORKFLOWS:p.workflow.setCurrentText(data['name'])
            elif action=='company' and set(data)=={'id'}:
                index=p.company.findData(data['id'])
                if index<0:raise ValueError('شرکت در دسترس نیست.')
                p.company.setCurrentIndex(index)
            elif action=='case' and set(data)=={'id'} and p.company_permitted():
                index=p.map_case.findData(data['id'])
                if index<0:raise ValueError('پرونده در دسترس نیست.')
                p.map_case.setCurrentIndex(index)
            elif action=='step' and set(data)=={'index'} and type(data['index']) is int and p.company_permitted():
                if not 0<=data['index']<len(WORKFLOWS.get(p.workflow.currentText(),())):raise ValueError('مرحله معتبر نیست.')
                p.open_map_step(data['index'])
            elif action=='complete_step' and set(data)=={'index','done'} and type(data['index']) is int and type(data['done']) is bool and p.company_permitted('edit'):
                p.set_step_done(data['index'],data['done'])
            elif action=='create' and not data and p.company_permitted('create'):p.add_workflow_case()
            elif action=='edit_case' and not data and p.company_permitted('edit'):
                if not p.select_map_case_row():raise ValueError('ابتدا پرونده را انتخاب کنید.')
                p.edit_case()
            elif action=='case_details' and not data and p.company_permitted():
                if not p.select_map_case_row():raise ValueError('ابتدا پرونده را انتخاب کنید.')
                p.details()
            elif action=='case_review' and not data and p.company_permitted():
                if not p.select_map_case_row():raise ValueError('ابتدا پرونده را انتخاب کنید.')
                p.review_case()
            elif action=='insured_people' and not data and p.company_permitted():
                if not p.select_map_case_row():raise ValueError('ابتدا پرونده را انتخاب کنید.')
                p.insured_people()
            elif action=='insurance_workshops' and not data and p.company_permitted() and p.workflow.currentText()=='بیمه کارکنان':
                p.insurance_workshops()
            elif action=='insurance_employee_profiles' and not data and p.company_permitted() and p.workflow.currentText()=='بیمه کارکنان':
                p.insurance_employee_profiles()
            elif action=='insurance_lists' and not data and p.company_permitted() and p.workflow.currentText()=='بیمه کارکنان':
                from insurance_monthly_ui import show_insurance_lists
                show_insurance_lists(p)
            elif action=='insurance_calculate' and p.company_permitted() and p.workflow.currentText()=='بیمه کارکنان':
                from insurance_preview import calculate_preview
                value=calculate_preview(data)
            elif action=='open_portal' and not data and p.company_permitted():
                category=p.workflow.currentText()
                url='https://es.tamin.ir/' if category=='بیمه کارکنان' else 'https://tp.tax.gov.ir/' if category=='سامانه مؤدیان' else 'https://my.tax.gov.ir/'
                QDesktopServices.openUrl(QUrl(url))
            elif action=='compare_invoices' and set(data)<={'start','end','portal_sales','portal_purchase'} and p.company_permitted():
                from tax_center import summarize_invoices, decimal
                from org_security import company_allowed
                from storage import fa, today_j, jformat, month_last_day
                actor=p.owner.session_user
                if actor is not None and not company_allowed(actor,p.company.currentData(),'clients','view'):
                    raise ValueError('دسترسی مالیات و فاکتورها برای همین شرکت لازم است.')
                today=today_j()
                start=(data.get('start') or jformat(today.replace(day=1))).strip()
                end=(data.get('end') or jformat(today.replace(day=month_last_day(today.year,today.month)))).strip()
                totals=summarize_invoices(p.owner.org.records,p.company.currentData(),start,end)
                sales_tax=totals['sales']['tax']-totals['sales_return']['tax']
                purchase_tax=totals['purchase']['tax']-totals['purchase_return']['tax']
                ps=str(data.get('portal_sales') or '').strip(); pp=str(data.get('portal_purchase') or '').strip()
                value={'start':fa(start),'end':fa(end),'rows':[
                    {'label':'فروش','count':fa(totals['sales']['count']),'base':fa(str(totals['sales']['base'])),'tax':fa(str(totals['sales']['tax'])),'total':fa(str(totals['sales']['total']))},
                    {'label':'برگشت از فروش','count':fa(totals['sales_return']['count']),'base':fa(str(totals['sales_return']['base'])),'tax':fa(str(totals['sales_return']['tax'])),'total':fa(str(totals['sales_return']['total']))},
                    {'label':'خرید','count':fa(totals['purchase']['count']),'base':fa(str(totals['purchase']['base'])),'tax':fa(str(totals['purchase']['tax'])),'total':fa(str(totals['purchase']['total']))},
                    {'label':'برگشت از خرید','count':fa(totals['purchase_return']['count']),'base':fa(str(totals['purchase_return']['base'])),'tax':fa(str(totals['purchase_return']['tax'])),'total':fa(str(totals['purchase_return']['total']))},
                ],'sales_tax':fa(str(sales_tax)),'purchase_tax':fa(str(purchase_tax)),'skipped':fa(totals['skipped']),
                'diff_sales':fa(str(sales_tax-decimal(ps))) if ps else '', 'diff_purchase':fa(str(purchase_tax-decimal(pp))) if pp else ''}
            elif action in ('all_cases','compare','tools') and not data and p.company_permitted():
                if not self.show_native:raise ValueError('نمای ابزارهای مالیات در دسترس نیست.')
                if action=='all_cases':p.show_workflow_cases()
                else:p.tabs.setCurrentIndex(2 if action=='compare' else 3)
                self.show_native()
            else:raise ValueError('این عملیات در دسترس نیست.')
            self.publish();result={'ok':True,'value':value}
        except Exception as exc:result={'ok':False,'error':str(exc)}
        self.completed.emit(request_id,json.dumps(result,ensure_ascii=False))
    def close(self):self.timer.stop()

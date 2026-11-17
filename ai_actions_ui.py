"""Human-readable review and editing for the assistant's allowlisted actions."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QPushButton,QLineEdit,QComboBox,QCheckBox,QDialogButtonBox)
from ai_app_actions import ACTION_LABELS,FIELD_LABELS,action_description,normalize_action
from ai_planning import REPEAT
from org_schema import STATUSES
from storage import fa
from reminders import effective_leads

def shown(key,value,context):
    if key=='assignee_id':return context['people'].get(value,{}).get('fullname','بدون مسئول' if not value else value)
    if key=='person_id':return next((p['name'] for p in context.get('public',{}).get('direct_people',[]) if p['id']==value),'همکار انتخاب‌شده')
    if key=='status':return STATUSES.get(value,value)
    if key=='direction':return {'income':'دریافت','expense':'پرداخت'}.get(value,value)
    if type(value) is bool:return 'بله' if value else 'خیر'
    if isinstance(value,list):return '، '.join(fa(n) for n in value)
    return fa(value)

def proposal_text(actions,context):
    lines=['در حال انجام درخواست:']
    for i,action in enumerate(actions):
        lines.append(fa(i+1)+' ـ '+ACTION_LABELS[action['type']]+' · '+action_description(action,context))
        lines.extend(FIELD_LABELS.get(key,key)+': '+shown(key,value,context) for key,value in action.get('changes',{}).items())
    return '\n\n'.join(lines)

class ActionEditor(QDialog):
    def __init__(self,owner,action,context):
        super().__init__(owner);self.action=copy.deepcopy(action);self.context=context;self.result_action=None;self.setWindowTitle('ویرایش پیشنهاد');self.setLayoutDirection(Qt.RightToLeft);self.resize(600,440);v=QVBoxLayout(self);v.addWidget(QLabel(action_description(action,context)));f=QFormLayout();v.addLayout(f);self.widgets={}
        for key,value in action.get('changes',{}).items():
            if type(value) is bool:w=QCheckBox();w.setChecked(value);kind='bool'
            elif key in ('status','recurrence','assignee_id','direction'):
                w=QComboBox();kind='choice'
                if key=='status':
                    for code,title in STATUSES.items():w.addItem(title,code)
                elif key=='recurrence':
                    for r in REPEAT:w.addItem(r,r)
                elif key=='direction':
                    w.addItem('دریافت','income');w.addItem('پرداخت','expense')
                else:
                    w.addItem('بدون مسئول','')
                    for p in context['people'].values():w.addItem(p['fullname'],p['id'])
                w.setCurrentIndex(max(0,w.findData(value)))
            else:w=QLineEdit(', '.join(map(str,value)) if isinstance(value,list) else str(value));kind='text'
            self.widgets[key]=(w,kind);f.addRow(FIELD_LABELS.get(key,key),w)
        self.error=QLabel();self.error.setWordWrap(True);v.addWidget(self.error);v.addStretch();buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('پذیرش ویرایش');buttons.button(QDialogButtonBox.Cancel).setText('انصراف');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def validate(self):
        try:
            for key,(w,kind) in self.widgets.items():
                value=w.isChecked() if kind=='bool' else w.currentData() if kind=='choice' else w.text()
                if key=='popup_seconds':value=int(value)
                self.action['changes'][key]=value
            self.result_action=normalize_action(self.action,self.context);self.accept()
        except (ValueError,PermissionError) as exc:self.error.setText(str(exc))

class ActionPreview(QDialog):
    def __init__(self,owner,actions,context):
        super().__init__(owner);self.owner=owner;self.actions=copy.deepcopy(actions);self.context=context;self.selected=[];self.setWindowTitle('بازبینی تغییرات دستیار');self.setLayoutDirection(Qt.RightToLeft);self.resize(940,530);v=QVBoxLayout(self);notice=QLabel('تغییرات زیر هنوز انجام نشده‌اند. موارد موردنظر را انتخاب کنید؛ پیشنهادها قابل ویرایش‌اند. فقط پس از زدن «اعمال موارد انتخاب‌شده» ذخیره می‌شوند.');notice.setWordWrap(True);v.addWidget(notice);self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['اعمال','عملیات','مورد','تغییر پیشنهادی']);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.verticalHeader().hide();self.table.setColumnWidth(0,45);self.table.setColumnWidth(1,135);self.table.setColumnWidth(2,225);self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch);self.table.itemDoubleClicked.connect(lambda _:self.edit());v.addWidget(self.table,1);edit=QPushButton('ویرایش پیشنهاد انتخابی');edit.clicked.connect(self.edit);v.addWidget(edit);self.error=QLabel();self.error.setWordWrap(True);v.addWidget(self.error);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('اعمال موارد انتخاب‌شده');b.button(QDialogButtonBox.Cancel).setText('انصراف');b.accepted.connect(self.validate);b.rejected.connect(self.reject);v.addWidget(b);self.draw()
    def draw(self):
        checked=[self.table.item(i,0).checkState()==Qt.Checked for i in range(self.table.rowCount())];self.table.setRowCount(len(self.actions))
        for i,action in enumerate(self.actions):
            check=QTableWidgetItem();check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Checked if i>=len(checked) or checked[i] else Qt.Unchecked);self.table.setItem(i,0,check)
            target=self.context['targets'].get(action.get('target'),{});old=self.context['settings'] if action['type']=='reminder_settings' else target.get('event') or target.get('record',{}).get('payload',{})
            if action['type']=='task_reminder':old=self.context.get('overrides',{}).get(target['record']['id'],{'lead_days':self.context['settings'].get('default_lead_days',[])})
            detail='\n'.join(FIELD_LABELS.get(k,k)+': '+shown(k,value,self.context)+('  (قبلی: '+shown(k,effective_leads(old,self.context['settings']) if k=='lead_days' and target.get('event') else old.get(k,''),self.context)+')' if action['type'] in ('reminder_settings','reminder_update','task_update','task_reminder') else '') for k,value in action.get('changes',{}).items())
            for j,text in enumerate((ACTION_LABELS[action['type']],action_description(action,self.context),detail or 'بازکردن صفحه'),1):self.table.setItem(i,j,QTableWidgetItem(text))
            self.table.setRowHeight(i,max(62,22*(len(action.get('changes',{}))+1)))
    def edit(self):
        i=self.table.currentRow()
        if i<0 or self.actions[i]['type']=='open_page':return
        d=ActionEditor(self.owner,self.actions[i],self.context)
        if d.exec()==QDialog.Accepted:self.actions[i]=d.result_action;self.draw()
    def validate(self):
        try:
            self.selected=[normalize_action(action,self.context) for i,action in enumerate(self.actions) if self.table.item(i,0).checkState()==Qt.Checked]
            if not self.selected:raise ValueError('حداقل یک مورد انتخاب کنید.')
            self.accept()
        except (ValueError,PermissionError) as exc:self.error.setText(str(exc))

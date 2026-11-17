"""Product groups and stock adjustments in the shared customer workspace."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QInputDialog,QMessageBox,QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QComboBox)

class InventoryPanel(QWidget):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.data={'groups':[],'products':[]};layout=QVBoxLayout(self);bar=QHBoxLayout();layout.addLayout(bar)
        for label,callback in [('گروه اصلی',lambda:self.group(False)),('گروه فرعی',lambda:self.group(True)),('کالای جدید',lambda:self.product(False)),('ویرایش کالا',lambda:self.product(True)),('اصلاح موجودی',self.adjust)]:
            b=QPushButton(label);b.clicked.connect(callback);bar.addWidget(b)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['کد کالا','نام کالا','گروه فرعی','واحد','قیمت خرید؛ ریال','قیمت فروش؛ ریال','موجودی']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);layout.addWidget(self.table)
        widths=panel.owner.data.setdefault('settings',{}).get('inventory_column_widths',[])
        for i,w in enumerate([110,220,170,85,160,160,110]):self.table.setColumnWidth(i,widths[i] if isinstance(widths,list) and len(widths)==7 and isinstance(widths[i],int) and 50<=widths[i]<=1000 else w)
        self.width_timer=QTimer(self);self.width_timer.setSingleShot(True);self.width_timer.setInterval(500);self.width_timer.timeout.connect(self.save_widths);self.table.horizontalHeader().sectionResized.connect(lambda *_:self.width_timer.start())
    def save_widths(self):
        self.panel.owner.data.setdefault('settings',{})['inventory_column_widths']=[self.table.columnWidth(i) for i in range(7)];self.panel.owner.persist()
    def request(self,path,payload=None,**query):
        from personalization_ui import request_wait
        return request_wait(self.panel.owner,path,payload,**query)
    def reload(self,quiet=False):
        company=self.panel.company.currentData()
        if not company or not self.panel.owner.org.client:return
        try:
            self.data=self.request('inventory',company=company,_quiet=quiet);self.data['products']=[p for p in self.data['products'] if p['active']];groups={g['id']:g['name'] for g in self.data['groups']};rows=self.data['products'];self.table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate([row['code'],row['name'],groups.get(row['group_id'],''),row['unit'],row['purchase_price'],row['sale_price'],row['balance']]):self.table.setItem(i,j,QTableWidgetItem(str(value)))
        except Exception as exc:
            if not quiet:QMessageBox.warning(self,'دریافت کالا',str(exc))
    def selected(self):
        i=self.table.currentRow();rows=self.data['products'];return rows[i] if 0<=i<len(rows) else None
    def group(self,sub):
        if not self.panel.ready('create'):return
        parent=None
        if sub:
            groups=[g for g in self.data['groups'] if not g['parent_id']]
            if not groups:QMessageBox.information(self,'گروه کالا','ابتدا گروه اصلی بسازید.');return
            name,ok=QInputDialog.getItem(self,'گروه اصلی','گروه اصلی', [g['name'] for g in groups],0,False)
            if not ok:return
            parent=next(g['id'] for g in groups if g['name']==name)
        name,ok=QInputDialog.getText(self,'گروه کالا','نام گروه فرعی' if sub else 'نام گروه اصلی')
        if not ok or not name.strip():return
        try:self.request('inventory/group',dict(company=self.panel.company.currentData(),name=name,parent_id=parent));self.reload()
        except Exception as exc:QMessageBox.warning(self,'ثبت گروه',str(exc))
    def product(self,edit):
        if not self.panel.ready('edit' if edit else 'create'):return
        old=self.selected() if edit else None
        if edit and not old:QMessageBox.information(self,'کالا','ابتدا کالا را انتخاب کنید.');return
        groups=[g for g in self.data['groups'] if g['parent_id']]
        if not groups:QMessageBox.information(self,'کالا','ابتدا گروه اصلی و فرعی بسازید.');return
        d=QDialog(self);d.setWindowTitle('ویرایش کالا' if edit else 'کالای جدید');f=QFormLayout(d);group=QComboBox();parents={g['id']:g['name'] for g in self.data['groups']}
        for g in groups:group.addItem(parents.get(g['parent_id'],'')+' / '+g['name'],g['id'])
        if old:group.setCurrentIndex(max(0,group.findData(old['group_id'])))
        f.addRow('گروه',group);fields={}
        for key,label,default in [('code','کد کالا',''),('name','نام کالا',''),('unit','واحد','عدد'),('purchase_price','قیمت خرید؛ ریال','0'),('sale_price','قیمت فروش؛ ریال','0')]:
            fields[key]=QLineEdit(str((old or {}).get(key,default)))
            if key=='code':
                fields[key].setReadOnly(True)
                if not old:fields[key].setText('خودکار از ۱۰۰۰')
            if key in ('purchase_price','sale_price'):fields[key].setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩]*'),fields[key]))
            f.addRow(label,fields[key])
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);f.addRow(buttons)
        if old and self.panel.can('delete'):
            remove=QPushButton('حذف کالا');f.addRow(remove)
            def archive():
                if QMessageBox.question(d,'حذف کالا','این کالا از فهرست فعال حذف شود؟ سوابق فاکتور و موجودی آن حفظ می‌شوند.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
                try:self.request('inventory/archive',dict(company=self.panel.company.currentData(),id=old['id'],version=old['version']));d.reject();self.reload()
                except Exception as exc:QMessageBox.warning(d,'حذف کالا',str(exc))
            remove.clicked.connect(archive)
        if d.exec()!=QDialog.Accepted:return
        payload={k:w.text().strip() for k,w in fields.items()};payload['group_id']=group.currentData()
        if not old:payload['code']='__AUTO__'
        try:self.request('inventory/product',dict(company=self.panel.company.currentData(),payload=payload,id=old['id'] if old else None,version=old['version'] if old else None));self.reload()
        except Exception as exc:QMessageBox.warning(self,'ثبت کالا',str(exc))
    def adjust(self):
        if not self.panel.ready('edit'):return
        row=self.selected()
        if not row:QMessageBox.information(self,'موجودی','ابتدا کالا را انتخاب کنید.');return
        dialog=QInputDialog(self);dialog.setWindowTitle('اصلاح موجودی');dialog.setLabelText('موجودی جدید (عدد منفی مجاز است):');dialog.setTextValue(str(row['balance']))
        editor=dialog.findChild(QLineEdit)
        if editor:editor.setValidator(QRegularExpressionValidator(QRegularExpression('-?[0-9۰-۹٠-٩]*(\\.[0-9۰-۹٠-٩]*)?'),editor))
        if dialog.exec()!=QDialog.Accepted:return
        value=dialog.textValue()
        reason,ok=QInputDialog.getText(self,'اصلاح موجودی','دلیل اصلاح:')
        if not ok:return
        try:self.request('inventory/adjust',dict(company=self.panel.company.currentData(),id=row['id'],version=row['version'],balance=value,reason=reason));self.reload()
        except Exception as exc:QMessageBox.warning(self,'اصلاح موجودی',str(exc))

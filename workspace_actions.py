"""Reviewed task creation shared by chat, minutes, documents and assistant."""
from PySide6.QtWidgets import QMessageBox,QDialog
from org_ui import RecordDialog

def task_draft(owner,title,notes='',message=None):
    panel=owner.org
    if not panel.client:QMessageBox.information(owner,'اتصال','برای ثبت کار به مرکز شرکت وارد شوید.');return
    if message:
        ix=panel.company.findData(message['company_id'])
        if ix>=0:panel.company.setCurrentIndex(ix)
    if not panel.company.currentData():QMessageBox.information(owner,'شرکت','ابتدا شرکت مربوط را انتخاب کنید.');return
    d=RecordDialog(panel,'task');d.widgets['title'][0].setText(title[:200]);d.widgets['notes'][0].setPlainText(notes[:30000]);d.widgets['status'][0].setCurrentIndex(d.widgets['status'][0].findData('draft'))
    if d.exec()==QDialog.Accepted:
        if message:owner.workspace.mutate('workspace/message-task',dict(id=message['id'],payload=dict(d.payload,company_id=panel.company.currentData())))
        else:panel.save_dialog(d)

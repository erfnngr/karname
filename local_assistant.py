"""Offline extractive assistance. Suggestions always require a human review."""
import re
from collections import Counter
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPlainTextEdit,QListWidget,QListWidgetItem,QPushButton,QLabel,QInputDialog,QMessageBox
from PySide6.QtCore import Qt
from workspace_store import clean

STOP=set('از به با در و یا که این آن را برای تا می شود شده است یک هم بر روی به‌صورت'.split())

def summarize(text,max_sentences=4):
    text=str(text).strip()[:100000];sentences=[x.strip() for x in re.split(r'(?<=[.!؟])\s+|\n+',text) if x.strip()]
    words=lambda t:[w for w in re.findall(r'\w+',clean(t)) if len(w)>2 and w not in STOP]
    counts=Counter(w for s in sentences for w in words(s));rank=sorted(range(len(sentences)),key=lambda i:sum(counts[w] for w in words(sentences[i]))/max(1,len(words(sentences[i]))),reverse=True)[:max_sentences]
    return [sentences[i] for i in sorted(rank)]

def task_suggestions(text):
    patterns=('باید','پیگیری','ارسال','بررسی','تهیه','انجام','پرداخت','تماس','مسئول','آماده','تحویل','ثبت','task','todo')
    sentences=[s.strip(' •-\t') for s in re.split(r'\n+|(?<=[.!؟])\s+',str(text)[:100000]) if s.strip()]
    result=[]
    for line in sentences:
        if any(w in clean(line) for w in patterns) and line not in result:result.append(line[:300])
    return result[:20]

class AssistantPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;v=QVBoxLayout(self);self.enabled=__import__('PySide6.QtWidgets',fromlist=['QCheckBox']).QCheckBox('دستیار محلی فعال باشد');self.enabled.setChecked(owner.data.get('preferences',{}).get('local_assistant',False));self.enabled.toggled.connect(self.toggle);v.addWidget(self.enabled);note=QLabel('متن گفتگو یا صورت‌جلسه را وارد کنید. خلاصه از جمله‌های خود متن انتخاب می‌شود و اطلاعاتی به بیرون فرستاده نمی‌شود. پیشنهادها پیش از ثبت بازبینی می‌شوند.');note.setWordWrap(True);v.addWidget(note);self.input=QPlainTextEdit();self.input.setPlaceholderText('متن برای خلاصه یا استخراج کار…');v.addWidget(self.input,1);row=QHBoxLayout()
        for title,fn in [('خلاصه متن',self.summary),('پیشنهاد کارها',self.tasks),('ساخت کار از مورد انتخابی',self.create)]:b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        v.addLayout(row);self.results=QListWidget();v.addWidget(self.results,1);self.toggle(self.enabled.isChecked(),save=False)
    def toggle(self,value,save=True):
        self.input.setEnabled(value);self.results.setEnabled(value)
        if save:self.owner.data.setdefault('preferences',{})['local_assistant']=value;self.owner.persist()
    def summary(self):
        if self.enabled.isChecked():self.results.clear();self.results.addItems(summarize(self.input.toPlainText()))
    def tasks(self):
        if self.enabled.isChecked():self.results.clear();self.results.addItems(task_suggestions(self.input.toPlainText()))
    def create(self):
        item=self.results.currentItem()
        if not self.enabled.isChecked() or not item:return
        from workspace_actions import task_draft
        task_draft(self.owner,item.text(),self.input.toPlainText())

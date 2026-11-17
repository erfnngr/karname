from datetime import date
import jdatetime
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QScrollArea,QComboBox,QFrame,QLineEdit
from storage import fa,MONTHS,jformat,today_j
from occasions import find_occasions
from karname_ui import MonthOverview

def label(value,name=None):
    w=QLabel(value);w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    if name:w.setObjectName(name)
    return w

class YearCombo(QComboBox):
    valueChanged=Signal(int)
    def __init__(self):
        super().__init__()
        for y in range(1300,1500):self.addItem(fa(y),y)
        self.currentIndexChanged.connect(lambda _:self.valueChanged.emit(self.value()))
    def value(self):return self.currentData()
    def setValue(self,value):self.setCurrentIndex(self.findData(value))

class OccasionsPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;v=QVBoxLayout(self);v.setContentsMargins(20,14,20,14);nav=QHBoxLayout();nav.addWidget(label('مناسبت‌ها','Hero'));nav.addStretch();self.year=YearCombo();self.year.setValue(owner.year);self.month=QComboBox();self.month.addItems(MONTHS);self.month.setCurrentIndex(owner.month-1);nav.addWidget(self.year);nav.addWidget(self.month);self.query=QLineEdit();self.query.setPlaceholderText('جستجو در همه ماه‌های سال');self.query.setMaximumWidth(245);self.query.setClearButtonEnabled(True);self.query.textChanged.connect(self.refresh);nav.addWidget(self.query);v.addLayout(nav);area=QScrollArea();area.setWidgetResizable(True);shell=QWidget();self.items=QVBoxLayout(shell);self.items.setAlignment(Qt.AlignTop);self.items.setSpacing(6);area.setWidget(shell);v.addWidget(area,1);self.year.valueChanged.connect(self.refresh);self.month.currentIndexChanged.connect(self.refresh);self.refresh()
    def refresh(self,*_):
        from features_ui import open_official
        while self.items.count():
            w=self.items.takeAt(0).widget()
            if w:w.hide();w.deleteLater()
        count=0
        query=self.query.text().strip();self.month.setEnabled(not query);self.rendered_items=find_occasions(self.year.value(),self.month.currentIndex()+1,query)
        for item in self.rendered_items:
            count+=1;card=QFrame();card.setObjectName('Panel');c=QHBoxLayout(card);c.setContentsMargins(12,8,12,8);c.addWidget(label(item['title']),1);jd=jdatetime.date.fromgregorian(date=item['date']);when=label(jformat(jd)+' · '+item['date'].isoformat(),'Sub');when.setWordWrap(False);c.addWidget(when);source=QPushButton('↗');source.setFixedWidth(32);source.setToolTip('منبع مناسبت');source.clicked.connect(lambda checked=False,u=item['source']:open_official(u));c.addWidget(source)
            if item.get('holiday'):
                dark=self.owner.data['settings']['theme']=='dark';card.setStyleSheet('QFrame {background:'+('#482936' if dark else '#FFECEF')+';border-radius:9px;} QLabel {color:'+('#FFB3C3' if dark else '#9F2635')+';}')
            self.items.addWidget(card)
        if not count:self.items.addWidget(label('مناسبتی در این انتخاب نیست.'))

"""Date-cell labels stay inside the calendar, including their first show event."""
from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import QLabel,QSizePolicy

class OccasionLabel(QLabel):
    def __init__(self,titles,parent=None,holiday=False):
        super().__init__(parent);self.full=' · '.join(titles);self.setObjectName('HolidayText' if holiday else 'OccasionText');self.setToolTip('\n'.join(titles));self.setTextFormat(Qt.PlainText);self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed);self.setMinimumWidth(0);self.setFixedHeight(19);self.setStyleSheet('font-size:10px;background:transparent;');self.fit()
    def resizeEvent(self,event):super().resizeEvent(event);self.fit()
    def fit(self):self.setText(self.fontMetrics().elidedText(self.full,Qt.ElideRight,max(8,self.width()-2)))
    def sizeHint(self):return QSize(10,19)

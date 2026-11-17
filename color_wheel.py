"""Circular HSV picker with explicit shade and hex entry."""
import math
from PySide6.QtCore import Qt,Signal,QPointF
from PySide6.QtGui import QColor,QImage,QPainter,QPen
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QSlider,QLabel,QLineEdit,QDialogButtonBox

class Wheel(QWidget):
    changed=Signal(QColor)
    def __init__(self,color):
        super().__init__();self.setFixedSize(240,240);self.color=QColor(color);self.image=QImage(240,240,QImage.Format_ARGB32);self.image.fill(Qt.transparent)
        for y in range(240):
            for x in range(240):
                dx=x-120;dy=y-120;s=math.hypot(dx,dy)/114
                if s<=1:self.image.setPixelColor(x,y,QColor.fromHsvF((math.atan2(-dy,dx)/(2*math.pi))%1,s,1))
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.drawImage(0,0,self.image);h,s,v,_=self.color.getHsvF();h=max(0,h);pt=QPointF(120+114*s*math.cos(h*2*math.pi),120-114*s*math.sin(h*2*math.pi));p.setPen(QPen(Qt.white,3));p.setBrush(self.color);p.drawEllipse(pt,6,6)
    def mousePressEvent(self,e):self.pick(e.position())
    def mouseMoveEvent(self,e):
        if e.buttons()&Qt.LeftButton:self.pick(e.position())
    def pick(self,pt):
        dx=pt.x()-120;dy=pt.y()-120;h=(math.atan2(-dy,dx)/(2*math.pi))%1;s=min(1,math.hypot(dx,dy)/114);self.color=QColor.fromHsvF(h,s,self.color.valueF());self.update();self.changed.emit(self.color)

class ColorWheelDialog(QDialog):
    def __init__(self,color,parent=None):
        super().__init__(parent);self.setWindowTitle('طیف رنگ');self.color=QColor(color);v=QVBoxLayout(self);self.wheel=Wheel(color);v.addWidget(self.wheel,alignment=Qt.AlignCenter)
        v.addWidget(QLabel('روشنایی رنگ'));self.value=QSlider(Qt.Horizontal);self.value.setRange(0,255);self.value.setValue(self.color.value());v.addWidget(self.value)
        self.hex=QLineEdit(self.color.name());self.hex.setLayoutDirection(Qt.LeftToRight);v.addWidget(self.hex);self.preview=QLabel('پیش‌نمایش');self.preview.setAlignment(Qt.AlignCenter);self.preview.setMinimumHeight(45);v.addWidget(self.preview)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('انتخاب');buttons.button(QDialogButtonBox.Cancel).setText('انصراف');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);v.addWidget(buttons)
        self.wheel.changed.connect(self.update_color);self.value.valueChanged.connect(self.shade);self.hex.editingFinished.connect(self.from_hex);self.update_color(self.color)
    def update_color(self,c):
        from appearance import contrast
        self.color=QColor(c);self.hex.setText(c.name());foreground=max(('#152A40','#FFFFFF'),key=lambda fg:contrast(fg,c.name()));self.preview.setStyleSheet('background:'+c.name()+';color:'+foreground+';border-radius:8px;')
    def shade(self,value):
        h,s,_,_=self.color.getHsvF();c=QColor.fromHsvF(max(h,0),s,value/255);self.wheel.color=c;self.wheel.update();self.update_color(c)
    def from_hex(self):
        color=QColor(self.hex.text())
        if color.isValid():
            self.wheel.color=color;self.wheel.update();self.value.blockSignals(True);self.value.setValue(color.value());self.value.blockSignals(False);self.update_color(color)
        else:self.hex.setText(self.color.name())
    @staticmethod
    def choose(color,parent=None):
        dialog=ColorWheelDialog(color,parent)
        return dialog.color.name() if dialog.exec()==QDialog.Accepted else None

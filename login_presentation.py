"""Modern frosted-glass sign-in card with ocean mist backdrop, persistent labels, and visible keyboard focus."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QScrollArea,
    QWidget,
)


def _install_glass_backdrop(dialog, dark=False):
    """Keep login dialog clean with an understated flat solid surface (no background photo)."""
    dialog.setAttribute(Qt.WA_StyledBackground, True)


def polish(dialog):
    dialog.setObjectName('KarnameLogin')
    card = dialog.findChild(QFrame, 'LoginCard')
    layout = card.layout()
    dialog.setMinimumSize(460, 520)
    screen = QApplication.primaryScreen().availableGeometry()
    dialog.resize(min(560, screen.width() - 32), min(810 if dialog.initial else 690, screen.height() - 40))
    for label in card.findChildren(QLabel):
        if label.objectName() == 'Hero':
            label.setText('به کارنامه خوش آمدید')
            label.setObjectName('LoginWelcome')
            label.setWordWrap(True)
    dialog.intro.setObjectName('LoginIntro')
    dialog.status.setObjectName('LoginStatus')
    dialog.status.setMinimumHeight(35)
    dialog.status.setTextFormat(Qt.PlainText)
    dialog.form.setRowWrapPolicy(QFormLayout.WrapAllRows)
    dialog.form.setVerticalSpacing(7)
    dialog.form.setHorizontalSpacing(0)
    dialog.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    index = layout.indexOf(dialog.form)
    layout.removeItem(dialog.form)
    dialog.form.setParent(None)
    body = QWidget()
    body.setObjectName('LoginFields')
    body.setLayout(dialog.form)
    area = QScrollArea()
    area.setObjectName('LoginFormScroll')
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(body)
    layout.insertWidget(index, area, 1)
    dialog.form_area = area
    layout.setSpacing(10)
    layout.setContentsMargins(28, 22, 28, 22)
    for field, title in [
        (dialog.username, 'نام کاربری'),
        (dialog.password, 'رمز عبور'),
        (dialog.first, 'نام'),
        (dialog.last, 'نام خانوادگی'),
        (dialog.confirm, 'تکرار رمز'),
    ]:
        field.setAccessibleName(title)
        field.setMinimumHeight(24)

    dark = bool(QApplication.instance() and QApplication.instance().property('karname_dark'))
    eye = QPixmap(24, 24)
    eye.fill(Qt.transparent)
    p = QPainter(eye)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor('#93C5FD' if dark else '#4A657C'), 1.7))
    p.drawEllipse(3, 7, 18, 10)
    p.drawEllipse(10, 10, 4, 4)
    p.end()
    action = QAction(QIcon(eye), 'نمایش / پنهان‌کردن رمز', dialog.password)
    action.setCheckable(True)
    action.toggled.connect(lambda shown: dialog.password.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password))
    dialog.password.addAction(action, QLineEdit.TrailingPosition)
    dialog.password.returnPressed.connect(dialog.submit)
    dialog.confirm.returnPressed.connect(dialog.submit)
    submit = dialog.buttons.button(QDialogButtonBox.Ok)
    submit.setObjectName('LoginSubmit')
    submit.setDefault(True)
    submit.setMinimumWidth(180)
    shadow = QGraphicsDropShadowEffect(card)
    shadow.setBlurRadius(44)
    shadow.setOffset(0, 14)
    shadow.setColor(QColor(4, 18, 34, 90 if dark else 46))
    card.setGraphicsEffect(shadow)

    _install_glass_backdrop(dialog, dark=dark)

    if dark:
        dialog.setStyleSheet('''
            QDialog#KarnameLogin {background: #0F172A;}
            QFrame#LoginCard {background: #162235; border: 1px solid #2A3F5F; border-radius: 22px;}
            QFrame#LoginCard QLabel {background: transparent; color: #EDF7FF;}
            QLabel#LoginWelcome {font-size: 24px; font-weight: bold; color: #F0F9FF;}
            QLabel#LoginIntro {color: #A5C4D8; font-size: 12px;}
            QLabel#LoginStatus {color: #5CE0C8; font-size: 12px; padding: 6px 10px; background: rgba(12, 133, 116, 36); border-radius: 10px;}
            QWidget#LoginFields, QScrollArea#LoginFormScroll, QScrollArea#LoginFormScroll QWidget {background: transparent; border: 0;}
            QFrame#LoginCard QLineEdit, QFrame#LoginCard QComboBox {background: rgba(20, 42, 62, 220); color: #F1F8FF; border: 1px solid rgba(125, 211, 252, 70); padding: 9px 11px; border-radius: 11px; selection-background-color: #0EA5E9; selection-color: white;}
            QFrame#LoginCard QLineEdit:focus, QFrame#LoginCard QComboBox:focus {border: 2px solid #5CE0C8; background: rgba(22, 48, 70, 245);}
            QFrame#LoginCard QPushButton {background: rgba(26, 54, 78, 210); color: #DCF2FF; border: 1px solid rgba(125, 211, 252, 65); padding: 9px 14px; border-radius: 11px;}
            QFrame#LoginCard QPushButton:hover {background: rgba(34, 72, 102, 230);}
            QDialogButtonBox QPushButton {min-width: 96px;}
            QFrame#LoginCard QPushButton#LoginSubmit {background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0EA5E9,stop:1 #0C8574); color: white; border: 0; min-width: 156px;}
            QFrame#LoginCard QPushButton#LoginSubmit:hover {background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #38BDF8,stop:1 #10B981);}
            QFrame#LoginCard QPushButton:disabled {color: #7FA0B8; background: rgba(19, 38, 55, 160);}
        ''')
    else:
        dialog.setStyleSheet('''
            QDialog#KarnameLogin {background: #F4F7FB;}
            QFrame#LoginCard {background: #FFFFFF; border: 1px solid #DCE6F0; border-radius: 22px;}
            QFrame#LoginCard QLabel {background: transparent; color: #122E46;}
            QLabel#LoginWelcome {font-size: 24px; font-weight: bold; color: #0B354D;}
            QLabel#LoginIntro {color: #49677E; font-size: 12px;}
            QLabel#LoginStatus {color: #0D6E6B; font-size: 12px; padding: 6px 10px; background: rgba(14, 165, 233, 22); border-radius: 10px;}
            QWidget#LoginFields, QScrollArea#LoginFormScroll, QScrollArea#LoginFormScroll QWidget {background: transparent; border: 0;}
            QFrame#LoginCard QLineEdit, QFrame#LoginCard QComboBox {background: rgba(244, 250, 253, 230); color: #133148; border: 1px solid rgba(148, 184, 206, 175); padding: 9px 11px; border-radius: 11px; selection-background-color: #0C8574; selection-color: white;}
            QFrame#LoginCard QLineEdit:focus, QFrame#LoginCard QComboBox:focus {border: 2px solid #0EA5E9; background: #FFFFFF;}
            QFrame#LoginCard QPushButton {background: rgba(236, 246, 251, 225); color: #1B4B66; border: 1px solid rgba(186, 214, 230, 210); padding: 9px 14px; border-radius: 11px;}
            QFrame#LoginCard QPushButton:hover {background: rgba(220, 241, 248, 245); border-color: #0EA5E9;}
            QDialogButtonBox QPushButton {min-width: 96px;}
            QDialogButtonBox QPushButton:default {background: #0C8574; color: white; border: 0;}
            QFrame#LoginCard QPushButton#LoginSubmit {background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0C8574,stop:1 #0284C7); color: white; border: 0; min-width: 156px;}
            QFrame#LoginCard QPushButton#LoginSubmit:hover {background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0F9D88,stop:1 #0EA5E9);}
            QFrame#LoginCard QPushButton:disabled {color: #7A8F9F; background: #EDF1F5;}
        ''')
    dialog.username.setFocus()

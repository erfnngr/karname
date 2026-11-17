import os,time,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import Qt,QEvent,QCoreApplication,QPoint
from PySide6.QtGui import QHelpEvent,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton,QToolButton,QDialogButtonBox,QMessageBox,QMenu,QStyle
from appearance import apply_appearance,palette_for,contrast,accent_foreground
from flow_buttons import eligible,bezier,has_readable_label,FLOW_DURATION_MS,inverse_is_clearer
from theme_catalog import THEMES

class FlowButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def test_animation_and_click_work_in_each_theme_and_mode(self):
        for key,_,_ in THEMES:
            for mode in ('light','dark'):
                with self.subTest(theme=key,mode=mode):
                    settings={'theme_preset':key,'theme':mode,'font_size':13};apply_appearance(settings);colors=palette_for(settings)
                    self.assertGreaterEqual(contrast(colors['text'],colors['panel']),4.5);self.assertGreaterEqual(contrast(accent_foreground(colors['accent']),colors['accent']),4.5)
                    b=QPushButton('ثبت اطلاعات');b.setObjectName('Primary');b.setLayoutDirection(Qt.RightToLeft);b.resize(160,44);calls=[];b.clicked.connect(lambda:calls.append(1));b.show();self.app.processEvents()
                    QCoreApplication.sendEvent(b,QEvent(QEvent.Enter));QTest.qWait(300)
                    self.assertEqual(b._karname_flow_animation.duration(),FLOW_DURATION_MS);self.assertLess(FLOW_DURATION_MS,400)
                    deadline=time.monotonic()+2
                    while float(b._karname_flow_animation.currentValue() or 0)<.95 and time.monotonic()<deadline:QTest.qWait(25)
                    self.assertGreater(float(b._karname_flow_animation.currentValue()),.95);self.assertFalse(b.grab().isNull());QTest.mouseClick(b,Qt.LeftButton);self.assertEqual(calls,[1]);b.setFocus();QTest.keyClick(b,Qt.Key_Space);self.assertEqual(calls,[1,1])
                    b.setEnabled(False);QTest.mouseClick(b,Qt.LeftButton);self.assertEqual(calls,[1,1]);b.close();b.deleteLater()
    def test_text_icon_menu_checkable_and_disabled_buttons(self):
        apply_appearance({'theme':'light','theme_preset':'default'})
        controls=[QPushButton('بازگشت'),QToolButton(),QPushButton('تقویم'),QPushButton('')]
        controls[1].setIcon(self.app.style().standardIcon(QStyle.SP_DialogSaveButton));controls[3].setIcon(self.app.style().standardIcon(QStyle.SP_TrashIcon));menu=QMenu(controls[2]);menu.addAction('ماه جاری');controls[2].setMenu(menu);controls[0].setCheckable(True)
        for button in controls:
            self.assertTrue(eligible(button));button.resize(100,40);button.show();self.app.processEvents();QCoreApplication.sendEvent(button,QEvent(QEvent.Enter));QTest.qWait(300)
            overlay=button._karname_flow_overlay;self.assertTrue(overlay.isVisible());self.assertGreater(float(overlay.animation.currentValue()),.95);self.assertFalse(button.grab().isNull());QCoreApplication.sendEvent(button,QEvent(QEvent.Leave));QTest.qWait(300);self.assertFalse(overlay.isVisible())
        QTest.mouseClick(controls[0],Qt.LeftButton);self.assertTrue(controls[0].isChecked());controls[0].setEnabled(False);QCoreApplication.sendEvent(controls[0],QEvent(QEvent.Enter));self.assertFalse(controls[0]._karname_flow_overlay.isVisible());self.assertIs(controls[2].menu(),menu)
        for button in controls:button.close();button.deleteLater()
    def test_original_arrow_curve_overshoots_then_settles(self):
        self.assertGreater(bezier(.6,.34,1.56,.64,1),1)
        self.assertAlmostEqual(bezier(1,.34,1.56,.64,1),1,places=3)
        self.assertFalse(inverse_is_clearer(QColor('#111111'),QColor('#ffffff'),QColor('#ffffff'),.1))
        self.assertTrue(inverse_is_clearer(QColor('#111111'),QColor('#ffffff'),QColor('#ffffff'),.8))
    def test_shiny_navigation_preserves_click_and_selected_state(self):
        apply_appearance({'theme':'dark','theme_preset':'glass_mist'})
        button=QPushButton('تقویم');button.setProperty('flowShiny',True);button.setCheckable(True);calls=[];button.clicked.connect(lambda:calls.append(1));button.resize(120,40);button.show();self.app.processEvents();self.assertTrue(button._karname_shiny_overlay.isVisible());QTest.qWait(300)
        QTest.mouseClick(button,Qt.LeftButton);self.assertEqual(calls,[1]);self.assertTrue(button.isChecked());button.setEnabled(False);QTest.mouseClick(button,Qt.LeftButton);self.assertEqual(calls,[1]);button.close();button.deleteLater()
    def test_shiny_hover_keeps_icon_and_label_geometry_stable(self):
        for key,_,_ in THEMES:
            for mode in ('light','dark'):
                apply_appearance({'theme':mode,'theme_preset':key});button=QPushButton('تقویم');button.setIcon(self.app.style().standardIcon(QStyle.SP_DialogSaveButton));button.setProperty('flowShiny',True);button.resize(140,40);button.show();self.app.processEvents()
                before=(button.geometry(),button.iconSize(),button.text());QCoreApplication.sendEvent(button,QEvent(QEvent.Enter));QTest.qWait(FLOW_DURATION_MS+40)
                self.assertEqual((button.geometry(),button.iconSize(),button.text()),before);QCoreApplication.sendEvent(button,QEvent(QEvent.Leave));QTest.qWait(FLOW_DURATION_MS+40);self.assertEqual((button.geometry(),button.iconSize(),button.text()),before);button.close();button.deleteLater()
    def test_tooltips_only_for_icon_or_symbol_buttons(self):
        apply_appearance({'theme':'light','theme_preset':'default'});f=self.app._karname_flow_filter
        labeled=QPushButton('تنظیمات');labeled.setToolTip('تنظیمات');icon=QPushButton('');icon.setToolTip('تنظیمات');tool=QToolButton();tool.setText('تقویم');tool.setIcon(self.app.style().standardIcon(QStyle.SP_DialogSaveButton));tool.setToolButtonStyle(Qt.ToolButtonIconOnly);symbol=QPushButton('؟')
        self.assertTrue(has_readable_label(labeled));self.assertFalse(has_readable_label(icon));self.assertFalse(has_readable_label(tool));self.assertFalse(has_readable_label(symbol))
        event=QHelpEvent(QEvent.ToolTip,QPoint(1,1),QPoint(1,1));self.assertTrue(f.eventFilter(labeled,event));self.assertFalse(f.eventFilter(icon,event))

import test_v6_ui as fixtures
class ThemeSwitchIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.V6UiTests.setUpClass();cls.app=fixtures.V6UiTests.app
    setUp=fixtures.V6UiTests.setUp
    tearDown=fixtures.V6UiTests.tearDown
    pump=fixtures.V6UiTests.pump
    def test_shiny_theme_toggle_changes_and_restores_mode(self):
        button=self.win.theme_button;self.assertTrue(button.property('flowShiny'));before=self.win.data['settings']['theme']
        button.click();self.app.processEvents();self.assertNotEqual(self.win.data['settings']['theme'],before)
        button.click();self.app.processEvents();self.assertEqual(self.win.data['settings']['theme'],before)

if __name__=='__main__':unittest.main()

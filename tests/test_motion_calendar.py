import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import QEvent,QCoreApplication,QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton
from appearance import apply_appearance,palette_for,contrast,accent_foreground
from theme_catalog import THEMES
from theme_dashboard import DashboardDay
from flow_buttons import emoji_only

class MotionCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_calendar_text_survives_hover_and_click_in_all_themes(self):
        for theme,_,_ in THEMES:
            for mode in ('light','dark'):
                with self.subTest(theme=theme,mode=mode):
                    settings={'theme_preset':theme,'theme':mode};apply_appearance(settings);c=palette_for(settings)
                    self.assertGreaterEqual(contrast(c['text'],c['hover']),4.5)
                    self.assertGreaterEqual(contrast(accent_foreground(c['accent']),c['accent']),4.5)
                    day=DashboardDay('۲۶',c['accent']);day.resize(34,34);day.show();clicked=[];day.clicked.connect(lambda:clicked.append(True));self.app.processEvents();font=day.font().toString()
                    QCoreApplication.sendEvent(day,QEnterEvent(QPointF(5,5),QPointF(5,5),QPointF(5,5)));QTest.qWait(190)
                    self.assertEqual(day.text(),'۲۶');self.assertEqual(day.font().toString(),font);self.assertFalse(hasattr(day,'_karname_flow_overlay'));self.assertGreater(float(day.motion.currentValue()),.9);day.click();self.assertTrue(clicked);self.assertFalse(day.grab().isNull());day.close();day.deleteLater()
    def test_emoji_hover_restores_font_without_changing_bounds(self):
        apply_appearance({'theme':'light','theme_preset':'default'});button=QPushButton('☀️');button.setText('🌤️');button.resize(40,36);button.show();self.app.processEvents();font=button.font().toString();bounds=button.size()
        self.assertTrue(emoji_only(button));QCoreApplication.sendEvent(button,QEvent(QEvent.Enter));QTest.qWait(200);self.assertEqual(button.size(),bounds)
        QCoreApplication.sendEvent(button,QEvent(QEvent.Leave));QTest.qWait(200);self.assertEqual(button.font().toString(),font);button.close()

if __name__=='__main__':unittest.main()

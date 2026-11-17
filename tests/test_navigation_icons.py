import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtGui import QPalette
from appearance import apply_appearance
from ui_icons import LUCIDE,symbol,iconize

class NavigationIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_nav_icons_are_available_and_distinct(self):
        keys=('home','check','invoice','desk','attendance','calendar','tax','calculator','news','company','chat','assistant')
        self.assertEqual(len({LUCIDE[k] for k in keys}),len(keys))
        for key in keys:
            self.assertFalse(symbol(key,'#17344d').isNull());self.assertFalse(symbol(key,'#ffffff').isNull())
    def test_action_icon_recolors_when_theme_changes(self):
        apply_appearance({'theme':'light','theme_preset':'default'})
        button=QPushButton('ذخیره');iconize(button,'save');before=button.icon().pixmap(26,26).toImage()
        apply_appearance({'theme':'dark','theme_preset':'default'});after=button.icon().pixmap(26,26).toImage()
        self.assertNotEqual(before,after);self.assertEqual(button.toolTip(),'ذخیره');button.deleteLater()

if __name__=='__main__':unittest.main()

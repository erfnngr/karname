import tempfile,unittest
from pathlib import Path
from PySide6.QtCore import QUrl
from react_design_host import bundled_url_allowed

class DesignHostPolicyTests(unittest.TestCase):
    def test_bundle_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'bundle';root.mkdir();page=root/'index.html';page.write_text('ok')
            outside=Path(d)/'secret.html';outside.write_text('secret')
            self.assertTrue(bundled_url_allowed(QUrl.fromLocalFile(str(page)),root))
            self.assertTrue(bundled_url_allowed(QUrl('karname-design://app/index.html'),root))
            self.assertFalse(bundled_url_allowed(QUrl('karname-design://evil/index.html'),root))
            self.assertFalse(bundled_url_allowed(QUrl('karname-design://app/../secret.html'),root))
            self.assertFalse(bundled_url_allowed(QUrl.fromLocalFile(str(outside)),root))
            self.assertFalse(bundled_url_allowed(QUrl('https://example.com'),root))
            self.assertTrue(bundled_url_allowed(QUrl('qrc:///qtwebchannel/qwebchannel.js'),root))
            self.assertTrue(bundled_url_allowed(QUrl('blob:karname-design://app/123'),root))
            self.assertFalse(bundled_url_allowed(QUrl('blob:https://example.com/123'),root))

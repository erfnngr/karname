"""Modern React Home dashboard panel backed by native Karname services."""
from pathlib import Path
from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from react_appearance_bridge import ReactAppearanceBridge
from react_design_host import BundledPage, shared_web_profile, sync_page_appearance
from react_home_bridge import ReactHomeBridge


class ReactHomeWidget(QWidget):
    showNativeRequested = Signal()

    def __init__(self, asset_dir, native_panel, parent=None):
        super().__init__(parent)
        root = Path(asset_dir).resolve()
        if not (root / 'home.html').is_file():
            raise FileNotFoundError('صفحه خانه جدید پیدا نشد.')
        self.view = QWebEngineView(self)
        self.profile = shared_web_profile(root, self.view)
        self.page = BundledPage(self.profile, root, self.view)
        sync_page_appearance(self.page, getattr(native_panel, 'owner', None), section='home')
        self.view.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = ReactHomeBridge(native_panel, self.page, show_native=self.showNativeRequested.emit)
        self.appearance = ReactAppearanceBridge(native_panel.owner, self.page, section='home', host=self)
        self.channel.registerObject('appearance', self.appearance)
        self.channel.registerObject('home', self.bridge)
        self.page.setWebChannel(self.channel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.load(QUrl('karname-design://app/home.html'))

    def closeEvent(self, event):
        self.bridge.close()
        super().closeEvent(event)

"""Embedded React EventManager x Jalali Calendar view."""
from pathlib import Path
from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from react_appearance_bridge import ReactAppearanceBridge
from react_calendar_bridge import ReactCalendarBridge
from react_design_host import BundledPage, shared_web_profile, sync_page_appearance


class ReactCalendarWidget(QWidget):
    showNativeRequested = Signal()

    def __init__(self, asset_dir, native_panel, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        root = Path(asset_dir).resolve()
        if not (root / 'calendar.html').is_file():
            raise FileNotFoundError('صفحه تقویم جدید پیدا نشد.')
        self.view = QWebEngineView(self)
        self.profile = shared_web_profile(root, self.view)
        self.page = BundledPage(self.profile, root, self.view)
        sync_page_appearance(self.page, owner, section='calendar')
        self.view.setPage(self.page)
        self.channel = QWebChannel(self.page)
        native_panel.owner = owner
        self.bridge = ReactCalendarBridge(native_panel, self.page, show_native=self.showNativeRequested.emit)
        self.appearance = ReactAppearanceBridge(owner, self.page, section='calendar', host=self)
        self.channel.registerObject('appearance', self.appearance)
        self.channel.registerObject('calendar', self.bridge)
        self.page.setWebChannel(self.channel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.load(QUrl('karname-design://app/calendar.html'))

    def closeEvent(self, event):
        self.bridge.close()
        super().closeEvent(event)

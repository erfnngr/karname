"""Embedded React chat, staged for integration after feature parity checks."""
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from react_appearance_bridge import ReactAppearanceBridge
from react_design_host import BundledPage, confirm_download, shared_web_profile, sync_page_appearance
from react_chat_bridge import ReactChatBridge


class ReactChatWidget(QWidget):
    def __init__(self, asset_dir, native_chat, parent=None):
        super().__init__(parent)
        root = Path(asset_dir).resolve()
        if not (root / 'live.html').is_file():
            raise FileNotFoundError('صفحه چت جدید پیدا نشد.')
        self.view = QWebEngineView(self)
        self.profile = shared_web_profile(root, self.view)
        self.page = BundledPage(self.profile, root, self.view)
        sync_page_appearance(self.page, getattr(native_chat, 'owner', None), section='chat')
        self.view.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = ReactChatBridge(native_chat.client, self.page, native_reminder=native_chat.remind, native_task=native_chat.task)
        self.appearance=ReactAppearanceBridge(native_chat.owner,self.page,section='chat',host=self);self.channel.registerObject('appearance',self.appearance)
        self.channel.registerObject('chat', self.bridge)
        self.page.setWebChannel(self.channel)
        if not getattr(self.profile, '_karname_download_hooked', False):
            self.profile._karname_download_hooked = True
            self.profile.downloadRequested.connect(
                lambda download: confirm_download(download, download.page().view() if download.page() else None)
            )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.load(QUrl('karname-design://app/live.html'))

    def closeEvent(self, event):
        self.bridge.close()
        super().closeEvent(event)

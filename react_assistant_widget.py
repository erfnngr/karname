"""Staged web presentation for the existing native assistant panel."""
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from react_appearance_bridge import ReactAppearanceBridge
from react_design_host import BundledPage, shared_web_profile, sync_page_appearance
from react_assistant_bridge import ReactAssistantBridge


class ReactAssistantWidget(QWidget):
    def __init__(self, asset_dir, native_panel, parent=None):
        super().__init__(parent)
        root=Path(asset_dir).resolve()
        if not (root/'assistant.html').is_file():raise FileNotFoundError('صفحه دستیار جدید پیدا نشد.')
        self.view=QWebEngineView(self);self.profile=shared_web_profile(root,self.view)
        self.page=BundledPage(self.profile,root,self.view);sync_page_appearance(self.page,getattr(native_panel,'owner',None),section='assistant');self.view.setPage(self.page)
        self.channel=QWebChannel(self.page);self.bridge=ReactAssistantBridge(native_panel,self.page)
        self.appearance=ReactAppearanceBridge(native_panel.owner,self.page,section='assistant',host=self);self.channel.registerObject('appearance',self.appearance)
        self.channel.registerObject('assistant',self.bridge);self.page.setWebChannel(self.channel)
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.addWidget(self.view)
        self.view.load(QUrl('karname-design://app/assistant.html'))

    def closeEvent(self,event):
        self.bridge.close();super().closeEvent(event)
